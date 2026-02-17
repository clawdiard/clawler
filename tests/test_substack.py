"""Tests for Substack source."""
from unittest.mock import patch
from clawler.sources.substack import SubstackSource, SUBSTACK_FEEDS

SAMPLE_SUBSTACK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>Test Newsletter</title>
    <item>
      <title>Deep Dive into LLMs</title>
      <link>https://test.substack.com/p/deep-dive-llms</link>
      <description>A comprehensive look at large language models.</description>
      <dc:creator>Test Author</dc:creator>
      <pubDate>Mon, 16 Feb 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Weekly Roundup</title>
      <link>https://test.substack.com/p/weekly-roundup</link>
      <description>&lt;p&gt;This week in tech.&lt;/p&gt;</description>
      <pubDate>Sun, 15 Feb 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def test_substack_feeds_defined():
    assert len(SUBSTACK_FEEDS) >= 20
    for feed in SUBSTACK_FEEDS:
        assert "slug" in feed
        assert "source" in feed
        assert "category" in feed


def test_substack_parse_feed():
    src = SubstackSource()
    feed_info = {"slug": "test", "source": "Test Newsletter", "category": "tech"}
    with patch.object(src, "fetch_url", return_value=SAMPLE_SUBSTACK_RSS):
        articles = src._parse_feed(feed_info)
    assert len(articles) == 2
    assert articles[0].title == "Deep Dive into LLMs"
    assert articles[0].source == "Substack (Test Newsletter)"
    assert articles[0].category == "tech"
    assert articles[0].timestamp is not None
    assert "Test Author" in articles[0].summary


def test_substack_html_stripped():
    src = SubstackSource()
    feed_info = {"slug": "test", "source": "Test", "category": "tech"}
    with patch.object(src, "fetch_url", return_value=SAMPLE_SUBSTACK_RSS):
        articles = src._parse_feed(feed_info)
    # Second article has HTML tags in description — should be stripped
    assert "<p>" not in articles[1].summary


def test_substack_empty_feed():
    src = SubstackSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src._parse_feed({"slug": "empty", "source": "Empty", "category": "tech"})
    assert articles == []


def test_substack_max_per_feed():
    src = SubstackSource(max_per_feed=1)
    feed_info = {"slug": "test", "source": "Test", "category": "tech"}
    with patch.object(src, "fetch_url", return_value=SAMPLE_SUBSTACK_RSS):
        articles = src._parse_feed(feed_info)
    assert len(articles) == 1


def test_substack_crawl_aggregates():
    src = SubstackSource(feeds=[
        {"slug": "a", "source": "A", "category": "tech"},
        {"slug": "b", "source": "B", "category": "science"},
    ])
    with patch.object(src, "fetch_url", return_value=SAMPLE_SUBSTACK_RSS):
        articles = src.crawl()
    assert len(articles) == 4  # 2 per feed


def test_substack_invalid_xml():
    src = SubstackSource()
    with patch.object(src, "fetch_url", return_value="not xml at all"):
        articles = src._parse_feed({"slug": "bad", "source": "Bad", "category": "tech"})
    assert articles == []
