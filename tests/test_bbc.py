"""Tests for BBC News source."""
from unittest.mock import patch, MagicMock
from clawler.sources.bbc import BBCNewsSource, BBC_FEEDS

SAMPLE_BBC_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News - Technology</title>
    <item>
      <title>AI breakthrough changes everything</title>
      <link>https://www.bbc.co.uk/news/technology-12345</link>
      <description>Researchers announce major advance in artificial intelligence.</description>
      <pubDate>Mon, 16 Feb 2026 20:00:00 GMT</pubDate>
    </item>
    <item>
      <title>New chip design doubles performance</title>
      <link>https://www.bbc.co.uk/news/technology-12346</link>
      <description>A new semiconductor architecture promises 2x speed gains.</description>
      <pubDate>Mon, 16 Feb 2026 18:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def test_bbc_source_name():
    src = BBCNewsSource()
    assert src.name == "bbc"


def test_bbc_feeds_defined():
    assert len(BBC_FEEDS) >= 10
    for feed in BBC_FEEDS:
        assert "url" in feed
        assert "section" in feed
        assert "category" in feed
        assert feed["url"].startswith("https://feeds.bbci.co.uk/")


def test_bbc_section_filter():
    src = BBCNewsSource(sections=["Technology", "Science"])
    assert src.sections == ["technology", "science"]


def test_bbc_parse_feed():
    src = BBCNewsSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_BBC_RSS):
        articles = src._parse_feed({"url": "https://example.com/rss", "section": "technology", "label": "Technology", "category": "tech", "prominence": 0.50}, set())
    assert len(articles) == 2
    assert articles[0].title == "AI breakthrough changes everything"
    assert articles[0].source == "BBC News (Technology)"
    assert articles[0].category in ("tech", "ai")
    assert articles[0].timestamp is not None
    assert "bbc:section:technology" in articles[0].tags


def test_bbc_crawl_aggregates():
    src = BBCNewsSource(sections=["Technology"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_BBC_RSS):
        articles = src.crawl()
    assert len(articles) == 2


def test_bbc_empty_feed():
    src = BBCNewsSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src._parse_feed({"url": "https://example.com/rss", "section": "world", "label": "World", "category": "world", "prominence": 0.50}, set())
    assert articles == []


def test_bbc_limit():
    src = BBCNewsSource(limit=1)
    with patch.object(src, "fetch_url", return_value=SAMPLE_BBC_RSS):
        articles = src._parse_feed({"url": "https://example.com/rss", "section": "technology", "label": "Technology", "category": "tech", "prominence": 0.50}, set())
    assert len(articles) == 1


def test_bbc_in_cli_source_registry():
    """Ensure BBC is wired into CLI source registry."""
    from clawler.sources import BBCNewsSource as _BBC
    assert _BBC is not None


def test_bbc_in_engine_imports():
    """Ensure BBC can be imported from engine module."""
    from clawler.engine import BBCNewsSource as _BBC
    assert _BBC is not None
