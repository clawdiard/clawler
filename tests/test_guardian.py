"""Tests for The Guardian source."""
from unittest.mock import patch
from clawler.sources.guardian import GuardianSource

MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>The Guardian - Technology</title>
  <item>
    <title>Test Guardian Article</title>
    <link>https://www.theguardian.com/technology/2026/feb/16/test</link>
    <description>A test article from The Guardian.</description>
    <pubDate>Mon, 16 Feb 2026 09:00:00 GMT</pubDate>
    <author>Guardian Writer</author>
  </item>
  <item>
    <title>Second Guardian Story</title>
    <link>https://www.theguardian.com/technology/2026/feb/16/test2</link>
    <description>Another test.</description>
    <pubDate>Mon, 16 Feb 2026 08:30:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


class TestGuardianSource:
    def test_crawl_parses_articles(self):
        src = GuardianSource(sections=["technology"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Test Guardian Article"
        assert articles[0].source == "The Guardian (Technology)"
        assert articles[0].category == "tech"
        assert "guardian:technology" in articles[0].tags

    def test_empty_feed(self):
        src = GuardianSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_limit_respected(self):
        src = GuardianSource(sections=["technology"], limit=1)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 1

    def test_author_extracted(self):
        src = GuardianSource(sections=["technology"])
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert articles[0].author == "Guardian Writer"

    def test_html_stripped_from_summary(self):
        html_rss = MOCK_RSS.replace(
            "A test article from The Guardian.",
            "<p>An <em>important</em> story.</p>"
        )
        src = GuardianSource(sections=["technology"])
        with patch.object(src, "fetch_url", return_value=html_rss):
            articles = src.crawl()
        assert "<" not in articles[0].summary
