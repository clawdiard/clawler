"""Tests for Google News source (v8.1.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.googlenews import GoogleNewsSource, GOOGLE_NEWS_TOPICS, GOOGLE_NEWS_SEARCHES

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Top Stories - Google News</title>
  <item>
    <title>Major breakthrough in quantum computing - Reuters</title>
    <link>https://news.google.com/rss/articles/abc123</link>
    <description>Scientists announce a major step forward in quantum computing.</description>
    <pubDate>Sat, 15 Feb 2026 18:00:00 GMT</pubDate>
  </item>
  <item>
    <title>AI regulation framework proposed by EU - BBC News</title>
    <link>https://news.google.com/rss/articles/def456</link>
    <description>The European Union proposes new AI governance rules.</description>
    <pubDate>Sat, 15 Feb 2026 16:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Stock markets rally on positive earnings</title>
    <link>https://news.google.com/rss/articles/ghi789</link>
    <description>Markets see gains across the board.</description>
    <pubDate>Sat, 15 Feb 2026 14:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Empty</title></channel></rss>"""


class TestGoogleNewsSource:
    def test_init_defaults(self):
        src = GoogleNewsSource()
        assert src.name == "Google News"
        assert src.lang == "en"
        assert src.geo == "US"
        assert len(src.topics) > 0
        assert len(src.searches) > 0

    def test_init_custom(self):
        src = GoogleNewsSource(topics=[], searches=[], max_per_feed=3, lang="de", geo="DE")
        assert src.topics == []
        assert src.searches == []
        assert src.max_per_feed == 3
        assert src.lang == "de"
        assert src.geo == "DE"

    def test_feed_url_for_topic(self):
        src = GoogleNewsSource()
        url = src._feed_url_for_topic("ABC123")
        assert "news.google.com/rss/topics/ABC123" in url
        assert "hl=en" in url
        assert "gl=US" in url

    def test_feed_url_for_search(self):
        src = GoogleNewsSource()
        url = src._feed_url_for_search("artificial intelligence")
        assert "news.google.com/rss/search" in url
        assert "artificial" in url

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_parse_feed_returns_articles(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=10)
        articles = src._parse_feed("https://example.com/feed", "Test", "tech")
        assert len(articles) == 3
        assert articles[0].title == "Major breakthrough in quantum computing - Reuters"
        assert articles[0].category == "tech"
        assert articles[0].author == "Reuters"  # extracted from title suffix
        assert articles[0].timestamp is not None

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_max_per_feed_limit(self, mock_fetch):
        src = GoogleNewsSource(max_per_feed=2)
        articles = src._parse_feed("https://example.com/feed", "Test", "tech")
        assert len(articles) == 2

    @patch.object(GoogleNewsSource, "fetch_url", return_value=EMPTY_RSS)
    def test_empty_feed(self, mock_fetch):
        src = GoogleNewsSource()
        articles = src._parse_feed("https://example.com/feed", "Test", "tech")
        assert len(articles) == 0

    @patch.object(GoogleNewsSource, "fetch_url", return_value="")
    def test_fetch_failure(self, mock_fetch):
        src = GoogleNewsSource()
        articles = src._parse_feed("https://example.com/feed", "Test", "tech")
        assert len(articles) == 0

    @patch.object(GoogleNewsSource, "fetch_url", return_value="<not valid xml")
    def test_invalid_xml(self, mock_fetch):
        src = GoogleNewsSource()
        articles = src._parse_feed("https://example.com/feed", "Test", "tech")
        assert len(articles) == 0

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_combines_topics_and_searches(self, mock_fetch):
        topics = [{"topic": "T1", "name": "Top", "category": "world"}]
        searches = [{"query": "AI", "name": "AI News", "category": "tech"}]
        src = GoogleNewsSource(topics=topics, searches=searches, max_per_feed=10)
        articles = src.crawl()
        # 3 articles per feed × 2 feeds = 6
        assert len(articles) == 6
        assert mock_fetch.call_count == 2

    @patch.object(GoogleNewsSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_dedup_topic_ids(self, mock_fetch):
        """Duplicate topic IDs (with suffix) should be deduplicated."""
        topics = [
            {"topic": "ABC123", "name": "Science", "category": "science"},
            {"topic": "ABC123:science", "name": "Science Alt", "category": "science"},
        ]
        src = GoogleNewsSource(topics=topics, searches=[], max_per_feed=10)
        articles = src.crawl()
        # Only one feed should be fetched due to dedup
        assert mock_fetch.call_count == 1
        assert len(articles) == 3

    def test_publisher_extraction(self):
        """Publisher should be extracted from 'Title - Publisher' format."""
        src = GoogleNewsSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src._parse_feed("https://example.com", "Test", "tech")
            # First article has " - Reuters"
            assert articles[0].author == "Reuters"
            # Third article has no publisher suffix
            assert articles[2].author == ""

    def test_constants_defined(self):
        assert len(GOOGLE_NEWS_TOPICS) >= 5
        assert len(GOOGLE_NEWS_SEARCHES) >= 5
        for t in GOOGLE_NEWS_TOPICS:
            assert "topic" in t
            assert "name" in t
            assert "category" in t
        for s in GOOGLE_NEWS_SEARCHES:
            assert "query" in s
            assert "name" in s
            assert "category" in s


class TestGoogleNewsImport:
    def test_import_from_sources(self):
        from clawler.sources import GoogleNewsSource as GNS
        assert GNS is not None

    def test_in_all_list(self):
        from clawler.sources import __all__
        assert "GoogleNewsSource" in __all__
