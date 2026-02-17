"""Tests for Google News source enhancements (v10.19.0).

Covers: keyword category detection, quality scoring, multi-geo, URL dedup,
publisher reputation, filters, provenance tags, global limit.
"""
import pytest
from unittest.mock import patch
from clawler.sources.googlenews import (
    GoogleNewsSource,
    GOOGLE_NEWS_TOPICS,
    GOOGLE_NEWS_SEARCHES,
    _detect_category,
    _publisher_quality,
    _compute_quality,
    _PUBLISHER_REPUTATION,
)

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Top Stories - Google News</title>
  <item>
    <title>Major breakthrough in quantum computing - Reuters</title>
    <link>https://news.google.com/rss/articles/abc123</link>
    <description>Scientists announce a major step forward in quantum computing research.</description>
    <pubDate>Sat, 15 Feb 2026 18:00:00 GMT</pubDate>
  </item>
  <item>
    <title>AI regulation framework proposed by EU - BBC News</title>
    <link>https://news.google.com/rss/articles/def456</link>
    <description>The European Union proposes new AI governance rules for artificial intelligence.</description>
    <pubDate>Sat, 15 Feb 2026 16:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Stock markets rally on positive earnings</title>
    <link>https://news.google.com/rss/articles/ghi789</link>
    <description>Markets see gains across the board on strong quarterly earnings.</description>
    <pubDate>Sat, 15 Feb 2026 14:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Bitcoin surges past $100K milestone - CNBC</title>
    <link>https://news.google.com/rss/articles/jkl012</link>
    <description>Bitcoin cryptocurrency reaches new all-time high.</description>
    <pubDate>Sat, 15 Feb 2026 12:00:00 GMT</pubDate>
  </item>
  <item>
    <title>New cancer treatment shows promise in clinical trial - Nature</title>
    <link>https://news.google.com/rss/articles/mno345</link>
    <description>A novel drug therapy shows breakthrough results in cancer treatment clinical trial.</description>
    <pubDate>Sat, 15 Feb 2026 10:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""


class TestCategoryDetection:
    def test_ai_detection(self):
        assert _detect_category("OpenAI launches new large language model", "") == "ai"

    def test_security_detection(self):
        assert _detect_category("Major data breach exposes millions", "") == "security"

    def test_crypto_detection(self):
        assert _detect_category("Bitcoin hits new high", "cryptocurrency blockchain") == "crypto"

    def test_health_detection(self):
        assert _detect_category("New vaccine approved by FDA", "") == "health"

    def test_science_detection(self):
        assert _detect_category("NASA discovers new planet", "") == "science"

    def test_business_detection(self):
        assert _detect_category("Company reports record earnings", "quarterly revenue profit") == "business"

    def test_gaming_detection(self):
        assert _detect_category("PlayStation 6 announced", "gaming video game") == "gaming"

    def test_no_match_returns_none(self):
        assert _detect_category("Random boring title", "nothing interesting") is None

    def test_uses_description_too(self):
        assert _detect_category("Important announcement", "deep learning neural network model") == "ai"


class TestPublisherQuality:
    def test_known_publisher(self):
        assert _publisher_quality("Reuters") == 0.95

    def test_partial_match(self):
        score = _publisher_quality("BBC")
        assert score >= 0.80

    def test_unknown_publisher(self):
        assert _publisher_quality("Random Blog") == 0.50

    def test_empty_publisher(self):
        assert _publisher_quality("") == 0.50


class TestQualityScoring:
    def test_top_publisher_first_position(self):
        q = _compute_quality("Reuters", 0, 10)
        assert q >= 0.90

    def test_unknown_publisher_last_position(self):
        q = _compute_quality("Unknown Blog", 9, 10)
        assert q < 0.50

    def test_position_decay(self):
        q1 = _compute_quality("Reuters", 0, 10)
        q5 = _compute_quality("Reuters", 4, 10)
        q10 = _compute_quality("Reuters", 9, 10)
        assert q1 > q5 > q10

    def test_single_item_no_decay(self):
        q = _compute_quality("Reuters", 0, 1)
        assert q == _publisher_quality("Reuters")


class TestGoogleNewsInit:
    def test_defaults(self):
        src = GoogleNewsSource()
        assert src.lang == "en"
        assert src.geo == "US"
        assert src.geos is None
        assert src.min_quality == 0.0
        assert src.category_filter is None
        assert src.exclude_publishers is None
        assert src.global_limit is None

    def test_custom_params(self):
        src = GoogleNewsSource(
            geos=["US", "GB"], min_quality=0.5,
            category_filter=["ai", "security"],
            exclude_publishers=["Fox News"],
            global_limit=20,
        )
        assert src.geos == ["US", "GB"]
        assert src.min_quality == 0.5
        assert src.category_filter == ["ai", "security"]
        assert src.exclude_publishers == ["fox news"]
        assert src.global_limit == 20


class TestGoogleNewsParsing:
    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_parse_returns_articles(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        assert len(articles) == 5

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_keyword_category_override(self, mock_fetch):
        """AI article should be detected as 'ai' even though feed says 'tech'."""
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        ai_article = [a for a in articles if "AI regulation" in a.title][0]
        assert ai_article.category == "ai"

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crypto_detected(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        btc = [a for a in articles if "Bitcoin" in a.title][0]
        assert btc.category == "crypto"

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_health_detected(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        health = [a for a in articles if "cancer" in a.title][0]
        assert health.category == "health"

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_publisher_extracted(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        assert articles[0].author == "Reuters"

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_quality_scores_assigned(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        for a in articles:
            assert hasattr(a, "quality_score")
            assert 0 <= a.quality_score <= 1.0

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_provenance_tags(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "Test Feed", "tech", geo="US", seen_urls=set(), feed_type="topic")
        tags = articles[0].tags
        assert "gnews:geo:US" in tags
        assert "gnews:topic:Test Feed" in tags
        assert any(t.startswith("gnews:publisher:") for t in tags)
        assert any(t.startswith("gnews:category:") for t in tags)

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_search_feed_type_tag(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com", "AI News", "ai", seen_urls=set(), feed_type="search")
        assert any("gnews:search:AI News" in t for t in articles[0].tags)

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_url_dedup(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        seen = set()
        a1 = src._parse_feed("https://example.com", "Feed1", "tech", seen_urls=seen)
        a2 = src._parse_feed("https://example.com", "Feed2", "tech", seen_urls=seen)
        assert len(a1) == 5
        assert len(a2) == 0  # all URLs already seen

    @patch.object(GoogleNewsSource, "fetch_url", return_value=EMPTY_RSS)
    def test_empty_feed(self, mock_fetch):
        src = GoogleNewsSource()
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        assert len(articles) == 0

    @patch.object(GoogleNewsSource, "fetch_url", return_value="")
    def test_fetch_failure(self, mock_fetch):
        src = GoogleNewsSource()
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        assert len(articles) == 0


class TestGoogleNewsFilters:
    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_min_quality_filter(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10, min_quality=0.80)
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        for a in articles:
            assert a.quality_score >= 0.80

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_category_filter(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10, category_filter=["crypto"])
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        assert all(a.category == "crypto" for a in articles)
        assert len(articles) >= 1  # Bitcoin article

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_exclude_publishers(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10, exclude_publishers=["Reuters"])
        articles = src._parse_feed("https://example.com", "Test", "tech", seen_urls=set())
        assert not any(a.author == "Reuters" for a in articles)


class TestGoogleNewsCrawl:
    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_combines_feeds(self, mock_fetch):
        topics = [{"topic": "T1", "name": "Top", "category": "world"}]
        searches = [{"query": "AI", "name": "AI News", "category": "ai"}]
        src = GoogleNewsSource(topics=topics, searches=searches, max_per_feed=10)
        articles = src.crawl()
        # 5 unique from first feed, 0 from second (deduped)
        assert len(articles) == 5
        assert mock_fetch.call_count == 2

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_global_limit(self, mock_fetch):
        topics = [{"topic": "T1", "name": "Top", "category": "world"}]
        src = GoogleNewsSource(topics=topics, searches=[], max_per_feed=10, global_limit=3)
        articles = src.crawl()
        assert len(articles) == 3

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_quality_sorted_output(self, mock_fetch):
        topics = [{"topic": "T1", "name": "Top", "category": "world"}]
        src = GoogleNewsSource(topics=topics, searches=[], max_per_feed=10)
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_multi_geo(self, mock_fetch):
        topics = [{"topic": "T1", "name": "Top", "category": "world"}]
        src = GoogleNewsSource(topics=topics, searches=[], geos=["US", "GB"], max_per_feed=10)
        articles = src.crawl()
        # US feed returns 5 articles, GB feed returns 0 (same URLs, deduped)
        assert mock_fetch.call_count == 2
        geo_tags = set()
        for a in articles:
            for t in a.tags:
                if t.startswith("gnews:geo:"):
                    geo_tags.add(t)
        assert "gnews:geo:US" in geo_tags

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_dedup_topic_ids(self, mock_fetch):
        topics = [
            {"topic": "ABC123", "name": "Science", "category": "science"},
            {"topic": "ABC123:science", "name": "Science Alt", "category": "science"},
        ]
        src = GoogleNewsSource(topics=topics, searches=[], max_per_feed=10)
        articles = src.crawl()
        assert mock_fetch.call_count == 1


class TestConstants:
    def test_topics_defined(self):
        assert len(GOOGLE_NEWS_TOPICS) >= 5
        for t in GOOGLE_NEWS_TOPICS:
            assert "topic" in t and "name" in t and "category" in t

    def test_searches_expanded(self):
        assert len(GOOGLE_NEWS_SEARCHES) >= 15
        for s in GOOGLE_NEWS_SEARCHES:
            assert "query" in s and "name" in s and "category" in s

    def test_publisher_reputation_populated(self):
        assert len(_PUBLISHER_REPUTATION) >= 30


class TestImport:
    def test_import_from_sources(self):
        from clawler.sources import GoogleNewsSource as GNS
        assert GNS is not None
