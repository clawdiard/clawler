"""Tests for NPR source v10.41.0 enhancements."""
import types
from unittest.mock import patch, MagicMock

import pytest

from clawler.sources.npr import (
    NPRSource,
    NPR_FEEDS,
    KEYWORD_CATEGORIES,
    PROMINENT_AUTHORS,
    _detect_category,
    _compute_quality,
)


# --- Unit tests for helpers ---

class TestDetectCategory:
    def test_ai_keywords(self):
        assert _detect_category("OpenAI launches new ChatGPT model", "") == "ai"

    def test_security_keywords(self):
        assert _detect_category("Major data breach at hospital", "ransomware attack") == "security"

    def test_health_keywords(self):
        assert _detect_category("FDA approves new cancer drug", "clinical trial results") == "health"

    def test_environment_keywords(self):
        assert _detect_category("Climate change drives wildfire season", "") == "environment"

    def test_no_match(self):
        assert _detect_category("Local fair opens this weekend", "fun for families") is None

    def test_crypto(self):
        assert _detect_category("Bitcoin hits new high", "cryptocurrency market surges") == "crypto"

    def test_education(self):
        assert _detect_category("University tuition costs rising", "students face debt") == "education"

    def test_business(self):
        assert _detect_category("Federal Reserve raises interest rates", "inflation concerns") == "business"

    def test_gaming(self):
        assert _detect_category("Nintendo announces new console", "video game fans excited") == "gaming"

    def test_culture(self):
        assert _detect_category("Oscar nominations announced", "best film category") == "culture"


class TestComputeQuality:
    def test_first_position_high_prominence(self):
        q = _compute_quality(0, 10, 0.50, "", "world")
        assert 0.4 <= q <= 0.55

    def test_last_position_lower(self):
        q_first = _compute_quality(0, 10, 0.50, "", "world")
        q_last = _compute_quality(9, 10, 0.50, "", "world")
        assert q_first > q_last

    def test_prominent_author_boost(self):
        q_no = _compute_quality(0, 5, 0.45, "unknown reporter", "science")
        q_yes = _compute_quality(0, 5, 0.45, "Terry Gross", "science")
        assert q_yes > q_no

    def test_specific_category_boost(self):
        q_world = _compute_quality(0, 5, 0.45, "", "world")
        q_ai = _compute_quality(0, 5, 0.45, "", "ai")
        assert q_ai > q_world

    def test_score_capped_at_1(self):
        q = _compute_quality(0, 1, 0.95, "Mary Louise Kelly", "ai")
        assert q <= 1.0

    def test_score_never_negative(self):
        q = _compute_quality(99, 100, 0.30, "", "world")
        assert q >= 0.0


class TestNPRFeeds:
    def test_feed_count(self):
        assert len(NPR_FEEDS) == 18

    def test_all_have_required_keys(self):
        for f in NPR_FEEDS:
            assert "url" in f
            assert "section" in f
            assert "category" in f
            assert "prominence" in f
            assert 0.0 < f["prominence"] <= 1.0

    def test_sections_unique(self):
        sections = [f["section"] for f in NPR_FEEDS]
        assert len(sections) == len(set(sections))


class TestProminentAuthors:
    def test_all_lowercase(self):
        for a in PROMINENT_AUTHORS:
            assert a == a.lower()

    def test_known_hosts(self):
        assert "terry gross" in PROMINENT_AUTHORS
        assert "mary louise kelly" in PROMINENT_AUTHORS


# --- Integration-style tests with mocked feeds ---

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>NPR Test</title>
<item>
  <title>AI breakthrough changes medicine</title>
  <link>https://npr.org/ai-medicine</link>
  <description>OpenAI and hospitals collaborate on new deep learning diagnostic tools.</description>
  <pubDate>Wed, 19 Feb 2026 12:00:00 GMT</pubDate>
  <author>Terry Gross</author>
</item>
<item>
  <title>Local farm festival draws crowds</title>
  <link>https://npr.org/farm-fest</link>
  <description>The annual festival returned with music and food.</description>
  <pubDate>Wed, 19 Feb 2026 11:00:00 GMT</pubDate>
  <author>Unknown Reporter</author>
</item>
<item>
  <title>Climate change impacts wildfire risk</title>
  <link>https://npr.org/wildfire-risk</link>
  <description>Global warming drives longer wildfire seasons and drought.</description>
  <pubDate>Wed, 19 Feb 2026 10:00:00 GMT</pubDate>
  <author>Scott Simon</author>
</item>
</channel>
</rss>"""


class TestNPRCrawl:
    def _mock_source(self, sections=None, **kwargs):
        src = NPRSource(sections=sections, **kwargs)
        src.fetch_url = MagicMock(return_value=SAMPLE_RSS)
        return src

    def test_basic_crawl(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        assert len(articles) == 3

    def test_keyword_category_override(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        ai_article = [a for a in articles if "ai-medicine" in a.url][0]
        assert ai_article.category == "ai"

    def test_environment_category_detected(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        wildfire = [a for a in articles if "wildfire" in a.url][0]
        assert wildfire.category == "environment"

    def test_quality_scores_assigned(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        for a in articles:
            assert a.quality_score is not None
            assert 0 <= a.quality_score <= 1.0

    def test_prominent_author_tagged(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        terry = [a for a in articles if "ai-medicine" in a.url][0]
        assert "npr:prominent-author" in terry.tags

    def test_provenance_tags(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        a = articles[0]
        section_tags = [t for t in a.tags if t.startswith("npr:section:")]
        cat_tags = [t for t in a.tags if t.startswith("npr:category:")]
        assert len(section_tags) == 1
        assert len(cat_tags) == 1

    def test_rich_summary_format(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        terry = [a for a in articles if "ai-medicine" in a.url][0]
        assert "✍️" in terry.summary
        assert "📰" in terry.summary

    def test_min_quality_filter(self):
        src = self._mock_source(sections=["News"], min_quality=0.99)
        articles = src.crawl()
        assert len(articles) == 0

    def test_category_filter(self):
        src = self._mock_source(sections=["News"], category_filter=["ai"])
        articles = src.crawl()
        assert all(a.category == "ai" for a in articles)

    def test_exclude_sections(self):
        src = NPRSource(exclude_sections=["News", "Politics"])
        src.fetch_url = MagicMock(return_value=SAMPLE_RSS)
        articles = src.crawl()
        for a in articles:
            assert "npr:section:news" not in a.tags
            assert "npr:section:politics" not in a.tags

    def test_global_limit(self):
        src = self._mock_source(sections=["News"], global_limit=1)
        articles = src.crawl()
        assert len(articles) == 1

    def test_quality_sorted(self):
        src = self._mock_source(sections=["News"])
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    def test_cross_section_dedup(self):
        """Same URLs from two sections should be deduplicated."""
        src = NPRSource(sections=["news", "world"])
        src.fetch_url = MagicMock(return_value=SAMPLE_RSS)
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_empty_feed(self):
        src = NPRSource(sections=["News"])
        src.fetch_url = MagicMock(return_value="")
        articles = src.crawl()
        assert len(articles) == 0
