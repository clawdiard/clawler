"""Tests for Nature source v10.58.0 — enhanced multi-journal, quality scoring, keyword categories."""

import types
from unittest.mock import patch

import pytest

from clawler.sources.nature import (
    BOOSTED_CATEGORIES,
    KEYWORD_CATEGORIES,
    NATURE_FEEDS,
    SECTION_CATEGORY,
    TIER_BASE,
    NatureSource,
    _compute_quality,
    _detect_category,
    _truncate_at_sentence,
)

# ---------------------------------------------------------------------------
# Sample RSS XML
# ---------------------------------------------------------------------------

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">
<channel>
<title>Nature</title>
<item>
  <title><![CDATA[Deep learning model predicts protein folding with atomic accuracy]]></title>
  <link>https://www.nature.com/articles/s41586-025-00001-1</link>
  <description><![CDATA[A new deep learning approach achieves unprecedented accuracy in protein structure prediction. The model outperforms existing methods on benchmark datasets.]]></description>
  <pubDate>Thu, 20 Feb 2026 10:00:00 GMT</pubDate>
  <dc:creator><![CDATA[Jane Smith]]></dc:creator>
  <prism:doi>10.1038/s41586-025-00001-1</prism:doi>
  <category><![CDATA[Structural Biology]]></category>
  <category><![CDATA[Machine Learning]]></category>
</item>
<item>
  <title><![CDATA[CRISPR gene therapy shows promise in rare disease trial]]></title>
  <link>https://www.nature.com/articles/s41586-025-00002-2</link>
  <description><![CDATA[Phase 2 clinical trial demonstrates significant improvement in patients treated with CRISPR-based gene therapy for sickle cell disease.]]></description>
  <pubDate>Wed, 19 Feb 2026 14:00:00 GMT</pubDate>
  <dc:creator><![CDATA[John Doe]]></dc:creator>
  <category><![CDATA[Gene Therapy]]></category>
</item>
<item>
  <title><![CDATA[Arctic ice sheet collapse accelerating beyond projections]]></title>
  <link>https://www.nature.com/articles/s41586-025-00003-3</link>
  <description><![CDATA[New satellite data reveals that Arctic ice sheet loss is 40% faster than climate models predicted, with implications for sea level rise.]]></description>
  <pubDate>Tue, 18 Feb 2026 09:00:00 GMT</pubDate>
  <dc:creator><![CDATA[Alice Climate]]></dc:creator>
  <category><![CDATA[Climate Science]]></category>
</item>
</channel>
</rss>"""

SAMPLE_RSS_MEDICINE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Nature Medicine</title>
<item>
  <title><![CDATA[Novel cancer immunotherapy doubles survival rates]]></title>
  <link>https://www.nature.com/articles/nm-025-0001</link>
  <description><![CDATA[Breakthrough immunotherapy treatment shows remarkable results.]]></description>
  <pubDate>Thu, 20 Feb 2026 12:00:00 GMT</pubDate>
  <dc:creator><![CDATA[Dr. Oncologist]]></dc:creator>
</item>
</channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""


def _mock_fetch(url_map):
    """Create a mock fetch_url that returns different XML per URL."""
    def fetch(self, url, **kw):
        return url_map.get(url, "")
    return fetch


# ---------------------------------------------------------------------------
# Unit tests: helpers
# ---------------------------------------------------------------------------


class TestTruncateAtSentence:
    def test_short_text_unchanged(self):
        assert _truncate_at_sentence("Hello world.") == "Hello world."

    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence. " + "x" * 300
        result = _truncate_at_sentence(text, 50)
        assert result.endswith(".")
        assert len(result) <= 50

    def test_truncates_at_word_boundary(self):
        text = "word " * 100
        result = _truncate_at_sentence(text, 30)
        assert len(result) <= 31  # word boundary + ellipsis


class TestDetectCategory:
    def test_ai_keywords(self):
        assert _detect_category("Deep learning model for NLP", [], "nature") == "ai"

    def test_health_keywords(self):
        assert _detect_category("New cancer drug shows promise", [], "nature") == "health"

    def test_environment_keywords(self):
        assert _detect_category("Climate change accelerating", [], "nature") == "environment"

    def test_security_keywords(self):
        assert _detect_category("Biosecurity threats from pathogens", [], "nature") == "security"

    def test_section_fallback(self):
        assert _detect_category("A study of something", [], "medicine") == "health"

    def test_rss_categories_used(self):
        assert _detect_category("A study", ["Machine Learning", "AI"], "nature") == "ai"

    def test_default_fallback(self):
        assert _detect_category("Generic title", [], "nature") == "science"

    def test_prefers_specific_over_science(self):
        # "quantum" matches science, but if "machine learning" also present, ai wins
        assert _detect_category("Machine learning for quantum systems", [], "nature") == "ai"


class TestComputeQuality:
    def test_tier1_first_position(self):
        q = _compute_quality(1, 0, 10, "science")
        assert q == 0.8

    def test_tier1_last_position(self):
        q = _compute_quality(1, 9, 10, "science")
        assert q < 0.8
        assert q > 0.5

    def test_tier3_lower_than_tier1(self):
        q1 = _compute_quality(1, 0, 10, "science")
        q3 = _compute_quality(3, 0, 10, "science")
        assert q1 > q3

    def test_boosted_category(self):
        q_normal = _compute_quality(2, 0, 10, "science")
        q_boosted = _compute_quality(2, 0, 10, "ai")
        assert q_boosted > q_normal

    def test_single_item(self):
        q = _compute_quality(1, 0, 1, "science")
        assert q == 0.8


# ---------------------------------------------------------------------------
# Integration tests: crawl
# ---------------------------------------------------------------------------


class TestNatureSourceCrawl:
    def test_basic_crawl(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) == 3
        assert articles[0].title == "Deep learning model predicts protein folding with atomic accuracy"
        assert articles[0].author == "Jane Smith"

    def test_category_detection_in_crawl(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        cats = [a.category for a in articles]
        assert "ai" in cats  # deep learning
        assert "health" in cats  # CRISPR gene therapy
        assert "environment" in cats  # ice sheet

    def test_quality_scores_present(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        for a in articles:
            assert a.quality_score is not None
            assert 0 < a.quality_score <= 1.0

    def test_sorted_by_quality(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_provenance_tags(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        a = articles[0]
        assert any(t.startswith("nature:journal:") for t in a.tags)
        assert any(t.startswith("nature:category:") for t in a.tags)
        assert any(t.startswith("nature:author:") for t in a.tags)

    def test_doi_extraction(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        a = articles[0]
        assert any("nature:doi:" in t for t in a.tags)

    def test_rss_category_tags(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        a = articles[0]
        assert any(t.startswith("nature:tag:") for t in a.tags)

    def test_cross_feed_dedup(self):
        src = NatureSource(feeds=[
            {"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1},
            {"url": "https://www.nature.com/nature2.rss", "section": "research", "tier": 1},
        ])
        # Both feeds return same XML (same URLs)
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_min_quality_filter(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}],
            min_quality=0.85,
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        for a in articles:
            assert a.quality_score >= 0.85

    def test_category_filter(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}],
            category_filter=["health"],
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        for a in articles:
            assert a.category == "health"

    def test_exclude_sections(self):
        src = NatureSource(
            feeds=[
                {"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1},
                {"url": "https://www.nature.com/nm.rss", "section": "medicine", "tier": 1},
            ],
            exclude_sections=["medicine"],
        )
        url_map = {
            "https://www.nature.com/nature.rss": SAMPLE_RSS,
            "https://www.nature.com/nm.rss": SAMPLE_RSS_MEDICINE,
        }
        with patch.object(src, "fetch_url", side_effect=lambda url, **kw: url_map.get(url, "")):
            articles = src.crawl()
        sources = [a.source for a in articles]
        assert not any("Medicine" in s for s in sources)

    def test_global_limit(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}],
            global_limit=2,
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) == 2

    def test_empty_feed(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/empty.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=EMPTY_RSS):
            articles = src.crawl()
        assert articles == []

    def test_fetch_failure(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_summary_contains_author_and_journal(self):
        src = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        a = articles[0]
        assert "✍️" in a.summary
        assert "📰" in a.summary
        assert "Nature" in a.summary

    def test_multi_feed_crawl(self):
        src = NatureSource(feeds=[
            {"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1},
            {"url": "https://www.nature.com/nm.rss", "section": "medicine", "tier": 1},
        ])
        url_map = {
            "https://www.nature.com/nature.rss": SAMPLE_RSS,
            "https://www.nature.com/nm.rss": SAMPLE_RSS_MEDICINE,
        }
        with patch.object(src, "fetch_url", side_effect=lambda url, **kw: url_map.get(url, "")):
            articles = src.crawl()
        assert len(articles) == 4  # 3 from nature + 1 from medicine

    def test_tier_affects_quality(self):
        src_t1 = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1}]
        )
        src_t3 = NatureSource(
            feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 3}]
        )
        with patch.object(src_t1, "fetch_url", return_value=SAMPLE_RSS):
            arts_t1 = src_t1.crawl()
        with patch.object(src_t3, "fetch_url", return_value=SAMPLE_RSS):
            arts_t3 = src_t3.crawl()
        # Tier 1 articles should have higher quality on average
        avg_t1 = sum(a.quality_score for a in arts_t1) / len(arts_t1)
        avg_t3 = sum(a.quality_score for a in arts_t3) / len(arts_t3)
        assert avg_t1 > avg_t3


class TestNatureFeedConfig:
    def test_default_feeds_have_18_journals(self):
        assert len(NATURE_FEEDS) == 18

    def test_all_feeds_have_required_keys(self):
        for f in NATURE_FEEDS:
            assert "url" in f
            assert "section" in f
            assert "tier" in f

    def test_all_sections_mapped(self):
        for f in NATURE_FEEDS:
            assert f["section"] in SECTION_CATEGORY

    def test_tiers_valid(self):
        for f in NATURE_FEEDS:
            assert f["tier"] in TIER_BASE


class TestKeywordCoverage:
    def test_all_categories_have_keywords(self):
        for cat in KEYWORD_CATEGORIES:
            assert len(KEYWORD_CATEGORIES[cat]) >= 3

    def test_boosted_categories_in_keywords(self):
        for cat in BOOSTED_CATEGORIES:
            assert cat in KEYWORD_CATEGORIES
