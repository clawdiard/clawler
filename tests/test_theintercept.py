"""Tests for The Intercept source."""
from unittest.mock import patch
from clawler.sources.theintercept import TheInterceptSource, INTERCEPT_FEEDS

SAMPLE_INTERCEPT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The Intercept</title>
    <item>
      <title>NSA Program Exposed in New Documents</title>
      <link>https://theintercept.com/2026/02/19/nsa-program/</link>
      <description>Leaked files reveal a vast surveillance operation.</description>
      <pubDate>Wed, 19 Feb 2026 12:00:00 GMT</pubDate>
      <author>staff@theintercept.com</author>
    </item>
    <item>
      <title>Big Tech Lobbying Hits Record Levels</title>
      <link>https://theintercept.com/2026/02/19/big-tech-lobbying/</link>
      <description>Silicon Valley spent billions influencing policy.</description>
      <pubDate>Wed, 19 Feb 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def test_intercept_source_name():
    src = TheInterceptSource()
    assert src.name == "theintercept"


def test_intercept_feeds_defined():
    assert len(INTERCEPT_FEEDS) >= 1
    for feed in INTERCEPT_FEEDS:
        assert "url" in feed
        assert "section" in feed


def test_intercept_parse_feed():
    src = TheInterceptSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_INTERCEPT_RSS):
        articles = src._parse_feed(INTERCEPT_FEEDS[0])
    assert len(articles) == 2
    assert articles[0].title == "NSA Program Exposed in New Documents"
    assert articles[0].source.startswith("The Intercept")
    assert articles[0].quality_score == 0.85


def test_intercept_keyword_categorization():
    src = TheInterceptSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_INTERCEPT_RSS):
        articles = src._parse_feed(INTERCEPT_FEEDS[0])
    # "NSA" and "surveillance" should trigger security category
    assert articles[0].category == "security"
    # "Big Tech" should trigger tech category
    assert articles[1].category == "tech"


def test_intercept_empty_feed():
    src = TheInterceptSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src._parse_feed(INTERCEPT_FEEDS[0])
    assert articles == []


def test_intercept_crawl():
    src = TheInterceptSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_INTERCEPT_RSS):
        articles = src.crawl()
    assert len(articles) >= 2


def test_intercept_section_filter():
    src = TheInterceptSource(sections=["Latest"])
    assert src.sections == ["latest"]


def test_intercept_in_registry():
    from clawler.registry import get_entry
    entry = get_entry("theintercept")
    assert entry is not None
    assert entry.display_name == "The Intercept"
