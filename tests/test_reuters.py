"""Tests for the Reuters source."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.reuters import ReutersSource, REUTERS_FEEDS


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Reuters Business</title>
<item>
  <title>Global Markets Rally on Trade Talks</title>
  <link>https://www.reuters.com/business/global-markets-rally</link>
  <description>Markets rose sharply on Monday as trade negotiations resumed.</description>
  <pubDate>Mon, 16 Feb 2026 06:00:00 GMT</pubDate>
  <author>Reuters Staff</author>
</item>
<item>
  <title>Central Bank Holds Rates Steady</title>
  <link>https://www.reuters.com/business/central-bank-holds</link>
  <description>The central bank opted to keep interest rates unchanged.</description>
  <pubDate>Mon, 16 Feb 2026 05:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


class TestReutersSource:
    def test_init_default(self):
        src = ReutersSource()
        assert src.name == "reuters"
        assert src.sections is None
        assert src.limit == 15

    def test_init_sections(self):
        src = ReutersSource(sections=["Business", "Technology"])
        assert src.sections == ["business", "technology"]

    def test_feed_count(self):
        assert len(REUTERS_FEEDS) == 12

    def test_feed_sections(self):
        sections = {f["section"] for f in REUTERS_FEEDS}
        assert "Business" in sections
        assert "Technology" in sections
        assert "World" in sections

    def test_feed_categories(self):
        cats = {f["category"] for f in REUTERS_FEEDS}
        assert "business" in cats
        assert "tech" in cats
        assert "world" in cats

    @patch.object(ReutersSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_parse_feed(self, mock_fetch):
        src = ReutersSource(sections=["Business"])
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Global Markets Rally on Trade Talks"
        assert articles[0].source == "Reuters (Business)"
        assert articles[0].category == "business"
        assert articles[0].timestamp is not None
        assert "reuters:section:business" in articles[0].tags

    @patch.object(ReutersSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_section_filter(self, mock_fetch):
        src = ReutersSource(sections=["Technology"])
        articles = src.crawl()
        # Business feed not fetched since we filtered to Technology only
        assert mock_fetch.call_count == 1

    @patch.object(ReutersSource, "fetch_url", return_value="")
    def test_empty_response(self, mock_fetch):
        src = ReutersSource(sections=["Business"])
        articles = src.crawl()
        assert articles == []

    @patch.object(ReutersSource, "fetch_url", side_effect=Exception("Network error"))
    def test_error_handling(self, mock_fetch):
        src = ReutersSource(sections=["Business"])
        articles = src.crawl()
        assert articles == []

    @patch.object(ReutersSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_limit(self, mock_fetch):
        src = ReutersSource(sections=["Business"], limit=1)
        articles = src.crawl()
        assert len(articles) == 1

    @patch.object(ReutersSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_article_author(self, mock_fetch):
        src = ReutersSource(sections=["Business"])
        articles = src.crawl()
        assert articles[0].author == "Reuters Staff"
