"""Tests for AP News source."""
from unittest.mock import patch, MagicMock
from clawler.sources.apnews import APNewsSource

MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>AP News: Top News</title>
  <item>
    <title>Test AP Article</title>
    <link>https://apnews.com/article/test-123</link>
    <description>A test article from AP News.</description>
    <pubDate>Mon, 16 Feb 2026 08:00:00 GMT</pubDate>
    <author>AP Reporter</author>
  </item>
  <item>
    <title>Another AP Story</title>
    <link>https://apnews.com/article/test-456</link>
    <description>Another test article.</description>
    <pubDate>Mon, 16 Feb 2026 07:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


class TestAPNewsSource:
    def test_crawl_parses_articles(self):
        src = APNewsSource(sections=["top news"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Test AP Article"
        assert articles[0].source == "AP News (Top News)"
        assert articles[0].category == "world"
        assert "apnews:top news" in articles[0].tags

    def test_section_filter(self):
        src = APNewsSource(sections=["politics"])
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 2  # politics feed returns our mock

    def test_empty_feed(self):
        src = APNewsSource(limit=5)
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_limit_respected(self):
        src = APNewsSource(sections=["top news"], limit=1)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 1

    def test_author_extracted(self):
        src = APNewsSource(sections=["top news"])
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert articles[0].author == "AP Reporter"

    def test_summary_cleaned(self):
        html_rss = MOCK_RSS.replace(
            "A test article from AP News.",
            "<p>A <b>bold</b> article from AP.</p>"
        )
        src = APNewsSource(sections=["top news"])
        with patch.object(src, "fetch_url", return_value=html_rss):
            articles = src.crawl()
        assert "<" not in articles[0].summary
