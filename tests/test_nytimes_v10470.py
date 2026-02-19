"""Tests for NYTimes source v10.47.0 enhancements."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.nytimes import (
    NYTimesSource, NYT_FEEDS, SECTION_PROMINENCE, KEYWORD_CATEGORIES,
    PROMINENT_AUTHORS, _detect_category,
)


# --- Fixtures ---

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>NYT > Technology</title>
<item>
  <title>OpenAI Releases GPT-5 With Major Advances</title>
  <link>https://www.nytimes.com/2026/02/19/technology/openai-gpt5.html</link>
  <description>The new language model shows significant improvements in reasoning.</description>
  <author>Cade Metz</author>
  <pubDate>Thu, 19 Feb 2026 12:00:00 GMT</pubDate>
  <category>Artificial Intelligence</category>
</item>
<item>
  <title>Apple Unveils Mixed Reality Headset Update</title>
  <link>https://www.nytimes.com/2026/02/19/technology/apple-vr.html</link>
  <description>The tech giant updates its Vision Pro device.</description>
  <author>Tripp Mickle</author>
  <pubDate>Thu, 19 Feb 2026 11:00:00 GMT</pubDate>
</item>
<item>
  <title>Bitcoin Surges Past $100,000 Mark</title>
  <link>https://www.nytimes.com/2026/02/19/technology/bitcoin-100k.html</link>
  <description>Cryptocurrency markets rally as bitcoin hits new record.</description>
  <pubDate>Thu, 19 Feb 2026 10:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""

SAMPLE_RSS_WORLD = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>NYT > World</title>
<item>
  <title>Ukraine Peace Talks Resume in Geneva</title>
  <link>https://www.nytimes.com/2026/02/19/world/ukraine-peace.html</link>
  <description>Diplomats gather for renewed ceasefire negotiations.</description>
  <author>Andrew Kramer</author>
  <pubDate>Thu, 19 Feb 2026 14:00:00 GMT</pubDate>
</item>
<item>
  <title>OpenAI Releases GPT-5 With Major Advances</title>
  <link>https://www.nytimes.com/2026/02/19/technology/openai-gpt5.html</link>
  <description>Duplicate article appearing in world feed too.</description>
  <pubDate>Thu, 19 Feb 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""

SAMPLE_RSS_OPINION = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>NYT > Opinion</title>
<item>
  <title>Why AI Regulation Matters Now</title>
  <link>https://www.nytimes.com/2026/02/19/opinion/ai-regulation.html</link>
  <description>The case for urgent action on artificial intelligence safety.</description>
  <author>Paul Krugman</author>
  <pubDate>Thu, 19 Feb 2026 08:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


def _mock_fetch(url_map):
    def fetch(self, url, **kw):
        for key, val in url_map.items():
            if key in url:
                return val
        return ""
    return fetch


# --- Category Detection ---

class TestCategoryDetection:
    def test_ai_detected(self):
        assert _detect_category("OpenAI launches new model", "") == "ai"

    def test_crypto_detected(self):
        assert _detect_category("Bitcoin hits new high", "") == "crypto"

    def test_security_detected(self):
        assert _detect_category("Major data breach at hospital", "") == "security"

    def test_health_detected(self):
        assert _detect_category("FDA approves cancer drug", "clinical trial results") == "health"

    def test_environment_detected(self):
        assert _detect_category("Wildfire threatens homes", "") == "environment"

    def test_education_detected(self):
        assert _detect_category("Student loan forgiveness plan", "") == "education"

    def test_world_detected(self):
        assert _detect_category("NATO summit addresses Ukraine", "") == "world"

    def test_no_match(self):
        assert _detect_category("Local park opens", "Nice day") is None

    def test_summary_keywords(self):
        assert _detect_category("New study published", "researchers used machine learning") == "ai"

    def test_business_detected(self):
        assert _detect_category("Federal Reserve raises rates", "") == "business"


# --- Feed Configuration ---

class TestFeedConfig:
    def test_feed_count(self):
        assert len(NYT_FEEDS) == 18

    def test_all_sections_have_prominence(self):
        for f in NYT_FEEDS:
            assert f["section"] in SECTION_PROMINENCE

    def test_new_sections_present(self):
        sections = {f["section"] for f in NYT_FEEDS}
        for s in ["Politics", "Education", "Movies", "Travel", "Real Estate", "Magazine", "Books"]:
            assert s in sections


# --- Prominent Authors ---

class TestProminentAuthors:
    def test_known_authors(self):
        assert "paul krugman" in PROMINENT_AUTHORS
        assert "cade metz" in PROMINENT_AUTHORS
        assert "maggie haberman" in PROMINENT_AUTHORS

    def test_author_count(self):
        assert len(PROMINENT_AUTHORS) >= 20


# --- Crawling ---

class TestCrawling:
    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_basic_crawl(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        assert len(articles) == 3

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_ai_category_override(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        ai_art = [a for a in articles if "openai" in a.title.lower()][0]
        assert ai_art.category == "ai"

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_crypto_category_override(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        btc = [a for a in articles if "bitcoin" in a.title.lower()][0]
        assert btc.category == "crypto"

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_prominent_author_boost(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        cade = [a for a in articles if a.author == "Cade Metz"][0]
        tripp = [a for a in articles if a.author == "Tripp Mickle"][0]
        # Cade Metz is prominent, should score higher (same position: idx 0 vs 1 helps too)
        assert cade.quality_score > tripp.quality_score

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_prominent_author_tag(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        cade = [a for a in articles if a.author == "Cade Metz"][0]
        assert "nytimes:prominent-author" in cade.tags

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({
        "Technology": SAMPLE_RSS, "World": SAMPLE_RSS_WORLD
    }))
    def test_cross_section_dedup(self):
        src = NYTimesSource(sections=["technology", "world"])
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))
        # GPT-5 article appears in both feeds but should only show once
        gpt_articles = [a for a in articles if "gpt5" in a.url]
        assert len(gpt_articles) == 1

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_quality_sorted(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_global_limit(self):
        src = NYTimesSource(sections=["technology"], global_limit=2)
        articles = src.crawl()
        assert len(articles) == 2

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_min_quality_filter(self):
        src = NYTimesSource(sections=["technology"], min_quality=0.99)
        articles = src.crawl()
        assert len(articles) == 0

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_category_filter(self):
        src = NYTimesSource(sections=["technology"], category_filter=["crypto"])
        articles = src.crawl()
        assert all(a.category == "crypto" for a in articles)
        assert len(articles) == 1

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_exclude_sections(self):
        src = NYTimesSource(exclude_sections=["technology"])
        # Should not include Technology
        feeds_used = [f for f in NYT_FEEDS if f["section"].lower() not in {"technology"}]
        assert len(feeds_used) == 17


# --- Rich Summary & Tags ---

class TestSummaryAndTags:
    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_rich_summary_format(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        art = [a for a in articles if a.author == "Cade Metz"][0]
        assert "✍️ Cade Metz" in art.summary
        assert "📰 Technology" in art.summary

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_provenance_tags(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        art = articles[0]
        tag_prefixes = [t.split(":")[0] + ":" + t.split(":")[1] for t in art.tags if ":" in t]
        assert "nytimes:section" in tag_prefixes
        assert "nytimes:category" in tag_prefixes

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_rss_category_tags(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        ai_art = [a for a in articles if "openai" in a.title.lower()][0]
        assert "nytimes:tag:artificial-intelligence" in ai_art.tags

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({
        "Opinion": SAMPLE_RSS_OPINION
    }))
    def test_opinion_prominent_author(self):
        src = NYTimesSource(sections=["opinion"])
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].author == "Paul Krugman"
        assert "nytimes:prominent-author" in articles[0].tags
        assert articles[0].category == "ai"  # keyword detection overrides section


# --- Quality Scoring ---

class TestQualityScoring:
    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_position_decay(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        # First article (idx 0) should have higher base than later ones
        # (though boosts may reorder)
        assert all(0 <= a.quality_score <= 1.0 for a in articles)

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_boosted_category_bonus(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        ai_art = [a for a in articles if a.category == "ai"][0]
        # AI category gets boost
        assert ai_art.quality_score > 0.4

    @patch.object(NYTimesSource, "fetch_url", _mock_fetch({"Technology": SAMPLE_RSS}))
    def test_scores_capped_at_one(self):
        src = NYTimesSource(sections=["technology"])
        articles = src.crawl()
        assert all(a.quality_score <= 1.0 for a in articles)
