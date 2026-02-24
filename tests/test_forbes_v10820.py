"""Tests for enhanced Forbes source (v10.82.0).

Covers: section feeds, keyword categories, quality scoring,
prominent authors, dedup, filters, provenance tags.
"""
import re
from unittest.mock import MagicMock, patch

import pytest

from clawler.sources.forbes import (
    FORBES_FEEDS,
    PROMINENT_AUTHORS,
    SECTION_CATEGORY_MAP,
    ForbesSource,
    _BOOSTED_CATEGORIES,
    _CATEGORY_KEYWORDS,
    _detect_category,
    _truncate_at_sentence,
)

# ── Fixtures ───────────────────────────────────────────────────────────────

MOCK_ENTRY_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Forbes</title>
{items}
</channel>
</rss>"""

def _make_entry(title, link, author="", summary="", category_tags=None):
    cats = ""
    if category_tags:
        cats = "".join(f"<category>{c}</category>" for c in category_tags)
    return f"""<item>
<title>{title}</title>
<link>{link}</link>
<author>{author}</author>
<description>{summary}</description>
<pubDate>Mon, 24 Feb 2026 12:00:00 +0000</pubDate>
{cats}
</item>"""

def _make_feed(*entries):
    return MOCK_ENTRY_TEMPLATE.format(items="\n".join(entries))


# ── Section feed tests ─────────────────────────────────────────────────────

class TestSectionFeeds:
    def test_has_14_sections(self):
        assert len(FORBES_FEEDS) == 14

    def test_all_sections_have_prominence(self):
        for f in FORBES_FEEDS:
            assert "prominence" in f
            assert 0.0 < f["prominence"] <= 1.0

    def test_all_sections_in_category_map(self):
        for f in FORBES_FEEDS:
            assert f["section"] in SECTION_CATEGORY_MAP

    def test_new_sections_present(self):
        names = {f["section"] for f in FORBES_FEEDS}
        assert "Energy" in names
        assert "Real Estate" in names
        assert "Small Business" in names
        assert "Diversity & Inclusion" in names


# ── Category detection tests ───────────────────────────────────────────────

class TestCategoryDetection:
    def test_ai_detected(self):
        assert _detect_category("OpenAI launches new LLM model", "", "Business") == "ai"

    def test_security_detected(self):
        assert _detect_category("Major data breach at hospital", "", "Innovation") == "security"

    def test_crypto_detected(self):
        assert _detect_category("Bitcoin hits new all-time high", "", "Money") == "crypto"

    def test_health_detected(self):
        assert _detect_category("FDA approves new cancer drug", "", "Innovation") == "health"

    def test_science_detected(self):
        assert _detect_category("NASA launches new space telescope", "", "Business") == "science"

    def test_business_detected(self):
        assert _detect_category("Startup raises Series B funding", "", "AI") == "business"

    def test_world_detected(self):
        assert _detect_category("NATO holds emergency summit", "", "Business") == "world"

    def test_culture_detected(self):
        assert _detect_category("Oscar nominations announced for best film", "", "Business") == "culture"

    def test_education_detected(self):
        assert _detect_category("University launches online learning platform", "", "Business") == "education"

    def test_gaming_detected(self):
        assert _detect_category("Nintendo announces next-gen console", "", "Business") == "gaming"

    def test_environment_detected(self):
        assert _detect_category("Deforestation and biodiversity loss in the Amazon", "", "Business") == "environment"

    def test_fallback_to_section(self):
        assert _detect_category("Some generic news headline", "", "AI") == "ai"
        assert _detect_category("Some generic news headline", "", "Healthcare") == "health"

    def test_keywords_over_section(self):
        # Keyword should win over section default
        assert _detect_category("Ransomware attack hits company", "", "AI") == "security"


# ── Quality scoring tests ──────────────────────────────────────────────────

class TestQualityScoring:
    def setup_method(self):
        self.source = ForbesSource()

    def test_quality_range(self):
        q = self.source._compute_quality("AI", 0.55, 0, "", "tech")
        assert 0.0 <= q <= 1.0

    def test_position_decay(self):
        q0 = self.source._compute_quality("AI", 0.55, 0, "", "tech")
        q10 = self.source._compute_quality("AI", 0.55, 10, "", "tech")
        assert q0 > q10

    def test_prominent_author_boost(self):
        q_normal = self.source._compute_quality("AI", 0.55, 0, "Nobody", "tech")
        q_prominent = self.source._compute_quality("AI", 0.55, 0, "Thomas Brewster", "tech")
        assert q_prominent > q_normal

    def test_boosted_category_bonus(self):
        q_tech = self.source._compute_quality("AI", 0.55, 0, "", "tech")
        q_ai = self.source._compute_quality("AI", 0.55, 0, "", "ai")
        assert q_ai > q_tech

    def test_never_exceeds_one(self):
        # Max everything
        q = self.source._compute_quality("AI", 0.55, 0, "Thomas Brewster", "ai")
        assert q <= 1.0


# ── Truncation tests ───────────────────────────────────────────────────────

class TestTruncation:
    def test_short_text_unchanged(self):
        assert _truncate_at_sentence("Hello world.") == "Hello world."

    def test_long_text_truncated(self):
        text = "First sentence. " * 30
        result = _truncate_at_sentence(text, 300)
        assert len(result) <= 300
        assert result.endswith(".")

    def test_no_sentence_boundary(self):
        text = "a " * 200
        result = _truncate_at_sentence(text, 300)
        assert len(result) <= 300


# ── Filter tests ───────────────────────────────────────────────────────────

class TestFilters:
    def _crawl_with_mock(self, source, entries_per_feed):
        feed_xml = _make_feed(*entries_per_feed)
        with patch.object(source, "fetch_url", return_value=feed_xml):
            return source.crawl()

    def test_category_filter(self):
        src = ForbesSource(sections=["AI"], category_filter=["ai"])
        entries = [
            _make_entry("OpenAI launches GPT-5", "https://forbes.com/1", "Author A"),
            _make_entry("Generic business news", "https://forbes.com/2", "Author B"),
        ]
        articles = self._crawl_with_mock(src, entries)
        for a in articles:
            assert a.category == "ai"

    def test_min_quality_filter(self):
        src = ForbesSource(sections=["AI"], min_quality=0.9)
        entries = [
            _make_entry("Some article", "https://forbes.com/1"),
        ]
        articles = self._crawl_with_mock(src, entries)
        for a in articles:
            assert a.quality_score >= 0.9

    def test_global_limit(self):
        src = ForbesSource(sections=["AI"], global_limit=2)
        entries = [
            _make_entry(f"Article {i}", f"https://forbes.com/{i}") for i in range(10)
        ]
        articles = self._crawl_with_mock(src, entries)
        assert len(articles) <= 2

    def test_exclude_sections(self):
        src = ForbesSource(exclude_sections=["Lifestyle"])
        feeds = src._get_feeds()
        section_names = {f["section"] for f in feeds}
        assert "Lifestyle" not in section_names

    def test_all_sections_shortcut(self):
        src = ForbesSource(sections=["all"])
        feeds = src._get_feeds()
        assert len(feeds) == 14


# ── Deduplication tests ────────────────────────────────────────────────────

class TestDeduplication:
    def test_cross_section_dedup(self):
        src = ForbesSource(sections=["AI", "Innovation"])
        entry = _make_entry("Same Article", "https://forbes.com/same", "Author")
        feed_xml = _make_feed(entry)
        with patch.object(src, "fetch_url", return_value=feed_xml):
            articles = src.crawl()
        urls = [a.url for a in articles]
        assert urls.count("https://forbes.com/same") == 1


# ── Provenance tags tests ─────────────────────────────────────────────────

class TestProvenanceTags:
    def _get_article(self):
        src = ForbesSource(sections=["AI"])
        entry = _make_entry(
            "OpenAI GPT-5 launch", "https://forbes.com/ai1",
            "Thomas Brewster", "AI model details",
            category_tags=["Artificial Intelligence", "Tech"]
        )
        feed_xml = _make_feed(entry)
        with patch.object(src, "fetch_url", return_value=feed_xml):
            articles = src.crawl()
        assert len(articles) > 0
        return articles[0]

    def test_section_tag(self):
        a = self._get_article()
        assert any(t.startswith("forbes:section:") for t in a.tags)

    def test_category_tag(self):
        a = self._get_article()
        assert any(t.startswith("forbes:category:") for t in a.tags)

    def test_author_tag(self):
        a = self._get_article()
        assert any(t.startswith("forbes:author:") for t in a.tags)

    def test_prominent_author_tag(self):
        a = self._get_article()
        assert "forbes:prominent-author" in a.tags

    def test_rss_category_tags(self):
        a = self._get_article()
        assert any(t.startswith("forbes:tag:") for t in a.tags)


# ── Rich summary tests ────────────────────────────────────────────────────

class TestRichSummary:
    def test_summary_has_author(self):
        src = ForbesSource(sections=["AI"])
        entry = _make_entry("Title", "https://forbes.com/1", "John Doe", "Some description")
        with patch.object(src, "fetch_url", return_value=_make_feed(entry)):
            articles = src.crawl()
        assert "✍️ John Doe" in articles[0].summary

    def test_summary_has_section(self):
        src = ForbesSource(sections=["AI"])
        entry = _make_entry("Title", "https://forbes.com/1", "", "Some description")
        with patch.object(src, "fetch_url", return_value=_make_feed(entry)):
            articles = src.crawl()
        assert "📰 Forbes AI" in articles[0].summary


# ── Prominent authors tests ───────────────────────────────────────────────

class TestProminentAuthors:
    def test_has_at_least_20(self):
        assert len(PROMINENT_AUTHORS) >= 20

    def test_all_lowercase_keys(self):
        for name in PROMINENT_AUTHORS:
            assert name == name.lower()

    def test_boost_values_reasonable(self):
        for name, boost in PROMINENT_AUTHORS.items():
            assert 0.0 < boost <= 0.15


# ── Integration test ──────────────────────────────────────────────────────

class TestIntegration:
    def test_quality_sorted_output(self):
        src = ForbesSource(sections=["AI"])
        entries = [
            _make_entry(f"Article {i}", f"https://forbes.com/{i}") for i in range(5)
        ]
        with patch.object(src, "fetch_url", return_value=_make_feed(*entries)):
            articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_source_label_includes_section(self):
        src = ForbesSource(sections=["Cybersecurity"])
        entry = _make_entry("Test", "https://forbes.com/1")
        with patch.object(src, "fetch_url", return_value=_make_feed(entry)):
            articles = src.crawl()
        if articles:
            assert "Cybersecurity" in articles[0].source
