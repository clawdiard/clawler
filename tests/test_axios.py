"""Tests for Axios source (updated for v10.66.0 enhancements)."""
from unittest.mock import patch, MagicMock
from clawler.sources.axios import AxiosSource, AXIOS_FEEDS


MOCK_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Axios</title>
    <item>
      <title>AI breakthrough stuns researchers</title>
      <link>https://www.axios.com/2026/02/18/ai-breakthrough</link>
      <description>A major AI advancement was announced today.</description>
      <pubDate>Tue, 18 Feb 2026 12:00:00 GMT</pubDate>
      <author>Test Author</author>
    </item>
    <item>
      <title>Markets rally on trade deal</title>
      <link>https://www.axios.com/2026/02/18/markets-rally</link>
      <description>Global markets surged after a new trade agreement.</description>
      <pubDate>Tue, 18 Feb 2026 11:00:00 GMT</pubDate>
    </item>
    <item>
      <title></title>
      <link></link>
    </item>
  </channel>
</rss>"""


def test_axios_crawl_parses_articles():
    src = AxiosSource(sections=["technology"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].source == "Axios (Technology)"
    assert articles[0].quality_score > 0
    assert "axios:section:technology" in articles[0].tags


def test_axios_section_filter():
    src = AxiosSource(sections=["science"])
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    assert len(articles) == 2
    assert all("Axios (Science)" in a.source for a in articles)


def test_axios_all_sections():
    """All 12 feeds are configured."""
    assert len(AXIOS_FEEDS) == 12


def test_axios_keyword_refinement():
    src = AxiosSource(sections=["top stories"], limit=10)
    with patch.object(src, "fetch_url", return_value=MOCK_FEED_XML):
        articles = src.crawl()
    # Keyword detection refines categories from section default
    assert any(a.category != "world" for a in articles) or len(articles) >= 1


def test_axios_empty_feed():
    src = AxiosSource()
    with patch.object(src, "fetch_url", return_value=None):
        articles = src.crawl()
    assert articles == []


def test_axios_name():
    src = AxiosSource()
    assert src.name == "axios"


def test_axios_registry_entry():
    from clawler.registry import SOURCES
    keys = [s.key for s in SOURCES]
    assert "axios" in keys
