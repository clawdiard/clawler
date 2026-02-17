"""Tests for Medium source."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.medium import MediumSource, _strip_html, _parse_date, DEFAULT_TAG_FEEDS, DEFAULT_PUBLICATION_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Medium Feed</title>
    <item>
      <title>Understanding Transformers in 2026</title>
      <link>https://medium.com/@alice/understanding-transformers?source=rss</link>
      <dc:creator>Alice Smith</dc:creator>
      <pubDate>Sat, 15 Feb 2026 12:00:00 GMT</pubDate>
      <category>machine-learning</category>
      <category>ai</category>
      <description>&lt;p&gt;A deep dive into transformer architectures.&lt;/p&gt;</description>
    </item>
    <item>
      <title>Startup Lessons from Failure</title>
      <link>https://medium.com/@bob/startup-lessons</link>
      <dc:creator>Bob Jones</dc:creator>
      <pubDate>Fri, 14 Feb 2026 08:00:00 GMT</pubDate>
      <category>startup</category>
      <description>&lt;p&gt;What I learned from my failed startup.&lt;/p&gt;</description>
    </item>
    <item>
      <title></title>
      <link></link>
    </item>
  </channel>
</rss>"""


class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_empty(self):
        assert _strip_html("") == ""

    def test_entities(self):
        result = _strip_html("foo&amp;bar")
        assert "foo" in result


class TestParseDate:
    def test_rfc2822(self):
        dt = _parse_date("Sat, 15 Feb 2026 12:00:00 GMT")
        assert dt is not None
        assert dt.year == 2026

    def test_none(self):
        assert _parse_date("") is None
        assert _parse_date(None) is None


class TestMediumSource:
    def test_defaults(self):
        src = MediumSource()
        assert src.name == "medium"
        assert len(src.tag_feeds) == len(DEFAULT_TAG_FEEDS)
        assert len(src.publication_feeds) == len(DEFAULT_PUBLICATION_FEEDS)

    def test_build_feed_urls(self):
        src = MediumSource(tag_feeds=["ai"], publication_feeds=["better-programming"], user_feeds=["@alice"])
        urls = src._build_feed_urls()
        assert len(urls) == 3
        assert "tag/ai" in urls[0][0]
        assert "better-programming" in urls[1][0]
        assert "@alice" in urls[2][0]

    def test_parse_feed(self):
        src = MediumSource()
        articles = src._parse_feed(SAMPLE_RSS, "artificial-intelligence", "tag")
        assert len(articles) == 2
        assert articles[0].title == "Understanding Transformers in 2026"
        assert articles[0].author == "Alice Smith"
        assert "?" not in articles[0].url  # tracking params stripped
        assert articles[0].timestamp is not None
        assert any("machine-learning" in t for t in articles[0].tags)

    def test_parse_empty(self):
        src = MediumSource()
        assert src._parse_feed("", "test", "tag") == []
        assert src._parse_feed("<invalid", "test", "tag") == []

    @patch.object(MediumSource, "fetch_url")
    def test_crawl_deduplicates(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = MediumSource(tag_feeds=["ai", "ml"], publication_feeds=[], user_feeds=[])
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))  # no duplicates
