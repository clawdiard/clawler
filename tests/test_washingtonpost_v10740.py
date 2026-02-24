"""Tests for enhanced Washington Post source v10.74.0."""
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from clawler.sources.washingtonpost import (
    WashingtonPostSource,
    _detect_category,
    _truncate_at_sentence,
    _compute_quality,
    WAPO_FEEDS,
    PROMINENT_AUTHORS,
)


# ── Sample RSS (feedparser format) ─────────────────────────────────────
def _make_rss(entries, section="national"):
    """Build minimal RSS XML."""
    items = ""
    for e in entries:
        items += f"""<item>
            <title>{e.get('title','')}</title>
            <link>{e.get('link','')}</link>
            <description>{e.get('summary','')}</description>
            <author>{e.get('author','')}</author>
            <pubDate>Mon, 24 Feb 2026 04:00:00 GMT</pubDate>
            {''.join(f'<category>{t}</category>' for t in e.get('tags',[]))}
        </item>"""
    return f"""<?xml version="1.0"?>
    <rss version="2.0"><channel><title>WaPo {section}</title>{items}</channel></rss>"""


# ── Category detection ─────────────────────────────────────────────────
class TestCategoryDetection:
    def test_ai_detected(self):
        assert _detect_category("OpenAI launches GPT-5", "", [], "tech") == "ai"

    def test_security_detected(self):
        assert _detect_category("Major data breach at hospital", "", [], "tech") == "security"

    def test_crypto_detected(self):
        assert _detect_category("Bitcoin surges past $100K", "", [], "business") == "crypto"

    def test_health_detected(self):
        assert _detect_category("FDA approves new cancer drug", "", [], "tech") == "health"

    def test_environment_detected(self):
        assert _detect_category("Climate change accelerates wildfire season", "", [], "science") == "environment"

    def test_world_detected(self):
        assert _detect_category("NATO summit addresses Ukraine conflict", "", [], "tech") == "world"

    def test_education_detected(self):
        assert _detect_category("University tuition costs rising for students", "", [], "culture") == "education"

    def test_fallback_to_section(self):
        assert _detect_category("A lovely afternoon walk", "", [], "culture") == "culture"

    def test_tags_contribute(self):
        assert _detect_category("New development", "", ["blockchain", "defi"], "tech") == "crypto"

    def test_summary_contributes(self):
        assert _detect_category("New study released", "researchers found vaccine effective against pandemic", [], "tech") == "health"

    def test_boosted_category_priority(self):
        # ai gets boost over generic matches
        cat = _detect_category("AI security breach in machine learning system", "", [], "tech")
        assert cat in ("ai", "security")  # both valid, both boosted


# ── Truncation ─────────────────────────────────────────────────────────
class TestTruncation:
    def test_short_unchanged(self):
        assert _truncate_at_sentence("Hello world.") == "Hello world."

    def test_truncates_at_sentence(self):
        text = "First sentence. Second sentence. " + "x" * 300
        result = _truncate_at_sentence(text, 300)
        assert result.endswith(".")
        assert len(result) <= 300

    def test_ellipsis_fallback(self):
        text = "a" * 400
        result = _truncate_at_sentence(text, 300)
        assert result.endswith("...")


# ── Quality scoring ────────────────────────────────────────────────────
class TestQualityScoring:
    def test_first_position_higher(self):
        q1 = _compute_quality(0.55, 0, 10, "", "tech", "Title", "")
        q2 = _compute_quality(0.55, 9, 10, "", "tech", "Title", "")
        assert q1 > q2

    def test_prominent_author_boost(self):
        author = list(PROMINENT_AUTHORS)[0]
        q1 = _compute_quality(0.50, 0, 10, author, "tech", "Title here", "")
        q2 = _compute_quality(0.50, 0, 10, "unknown", "tech", "Title here", "")
        assert q1 > q2

    def test_boosted_category(self):
        q1 = _compute_quality(0.50, 0, 10, "", "ai", "Title", "")
        q2 = _compute_quality(0.50, 0, 10, "", "culture", "Title", "")
        assert q1 > q2

    def test_score_capped_at_1(self):
        q = _compute_quality(0.55, 0, 1, list(PROMINENT_AUTHORS)[0], "ai",
                             "A very long detailed title with many words here indeed", "x" * 200)
        assert q <= 1.0

    def test_single_article_no_decay(self):
        q = _compute_quality(0.55, 0, 1, "", "tech", "Title", "")
        assert q == pytest.approx(0.55, abs=0.01)


# ── Feed configuration ─────────────────────────────────────────────────
class TestFeedConfig:
    def test_14_sections(self):
        assert len(WAPO_FEEDS) == 14

    def test_all_sections_have_required_keys(self):
        for key, info in WAPO_FEEDS.items():
            assert "url" in info
            assert "label" in info
            assert "fallback_cat" in info
            assert "prominence" in info

    def test_new_sections_present(self):
        for s in ("health", "education", "lifestyle", "entertainment", "sports", "investigations", "science"):
            assert s in WAPO_FEEDS, f"Missing section: {s}"

    def test_prominent_authors_count(self):
        assert len(PROMINENT_AUTHORS) >= 20


# ── Crawl integration ─────────────────────────────────────────────────
class TestCrawl:
    def _make_source(self, entries_per_section=3, **kwargs):
        src = WashingtonPostSource(**kwargs)
        rss_data = {}
        for key, info in WAPO_FEEDS.items():
            entries = [
                {"title": f"Article {i} in {info['label']}", "link": f"https://wapo.com/{key}/{i}",
                 "summary": f"Summary for article {i} in section {info['label']}. This is a test.",
                 "author": "Test Author"}
                for i in range(entries_per_section)
            ]
            rss_data[info["url"]] = _make_rss(entries, key)

        original_fetch = src.fetch_url
        def mock_fetch(url):
            return rss_data.get(url, "")
        src.fetch_url = mock_fetch
        return src

    def test_crawl_all_sections(self):
        src = self._make_source()
        articles = src.crawl()
        assert len(articles) == 14 * 3  # 14 sections × 3 articles

    def test_crawl_specific_sections(self):
        src = self._make_source(sections=["national", "world"])
        articles = src.crawl()
        assert all("National" in a.source or "World" in a.source for a in articles)

    def test_deduplication(self):
        src = WashingtonPostSource()
        entries = [
            {"title": "Same Article", "link": "https://wapo.com/same", "summary": "Test", "author": "A"},
        ]
        rss = _make_rss(entries)
        for key, info in WAPO_FEEDS.items():
            pass  # just need the mock
        # Feed all sections the same URL
        def mock_fetch(url):
            return rss
        src.fetch_url = mock_fetch
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))  # no dupes

    def test_exclude_sections(self):
        src = self._make_source(exclude_sections=["opinions", "sports"])
        articles = src.crawl()
        for a in articles:
            assert "Opinions" not in a.source
            assert "Sports" not in a.source

    def test_min_quality_filter(self):
        src = self._make_source(min_quality=0.6)
        articles = src.crawl()
        assert all(a.quality_score >= 0.6 for a in articles)

    def test_category_filter(self):
        src = self._make_source(category_filter=["world"])
        articles = src.crawl()
        assert all(a.category == "world" for a in articles)

    def test_global_limit(self):
        src = self._make_source(global_limit=5)
        articles = src.crawl()
        assert len(articles) <= 5

    def test_quality_sorted_output(self):
        src = self._make_source()
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_provenance_tags(self):
        src = self._make_source(sections=["technology"])
        articles = src.crawl()
        assert len(articles) > 0
        a = articles[0]
        tag_str = " ".join(a.tags)
        assert "wapo:section:technology" in tag_str
        assert "wapo:category:" in tag_str
        assert "wapo:author:" in tag_str

    def test_rich_summary_format(self):
        src = self._make_source(sections=["national"])
        articles = src.crawl()
        a = articles[0]
        assert "✍️" in a.summary
        assert "📰" in a.summary

    def test_all_keyword_shortcut(self):
        src = self._make_source(sections=["all"])
        articles = src.crawl()
        assert len(articles) == 14 * 3
