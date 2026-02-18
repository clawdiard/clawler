"""Tests for CNBC and MarketWatch sources (v10.23.0)."""
from unittest.mock import patch, MagicMock
from clawler.sources.cnbc import CNBCSource, _quality_boost
from clawler.sources.marketwatch import MarketWatchSource


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Fed Raises Interest Rates by 25 Basis Points</title>
      <link>https://example.com/article1</link>
      <description>The Federal Reserve raised rates today.</description>
      <pubDate>Mon, 17 Feb 2026 12:00:00 GMT</pubDate>
      <author>Jane Doe</author>
    </item>
    <item>
      <title>Markets Rally on Earnings</title>
      <link>https://example.com/article2</link>
      <description>S&amp;P 500 hits new highs.</description>
      <pubDate>Mon, 17 Feb 2026 11:00:00 GMT</pubDate>
    </item>
    <item>
      <title></title>
      <link>https://example.com/noname</link>
    </item>
  </channel>
</rss>"""


class TestCNBCSource:
    def test_crawl_parses_articles(self):
        src = CNBCSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) >= 2
        assert articles[0].title == "Fed Raises Interest Rates by 25 Basis Points"
        assert articles[0].source.startswith("CNBC")
        assert articles[0].timestamp is not None
        assert articles[0].author == "Jane Doe"

    def test_crawl_filters_sections(self):
        src = CNBCSource(sections=["Technology"])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        # Only the Technology feed should be queried
        assert all("Technology" in a.source or "tech" in a.tags[0] for a in articles)

    def test_crawl_handles_empty_response(self):
        src = CNBCSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_crawl_handles_exception(self):
        src = CNBCSource()
        with patch.object(src, "fetch_url", side_effect=Exception("boom")):
            articles = src.crawl()
        assert articles == []

    def test_source_name(self):
        assert CNBCSource().name == "cnbc"

    def test_empty_title_skipped(self):
        src = CNBCSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        titles = [a.title for a in articles]
        assert "" not in titles

    def test_limit_parameter(self):
        src = CNBCSource(limit=1)
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        # Each feed returns at most 1 article
        per_feed = {}
        for a in articles:
            per_feed.setdefault(a.source, 0)
            per_feed[a.source] += 1
        for count in per_feed.values():
            assert count <= 1


class TestMarketWatchSource:
    def test_crawl_parses_articles(self):
        src = MarketWatchSource()
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
        assert len(articles) >= 2
        assert articles[0].source.startswith("MarketWatch")

    def test_crawl_handles_empty(self):
        src = MarketWatchSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_source_name(self):
        assert MarketWatchSource().name == "marketwatch"


class TestQualityBoost:
    def test_high_keyword(self):
        assert _quality_boost("Fed raises rates", "") == 0.15

    def test_medium_keyword(self):
        assert _quality_boost("Dow Jones closes flat", "") == 0.08

    def test_no_keyword(self):
        assert _quality_boost("Weather forecast", "") == 0.0


class TestRegistryIncludesNewSources:
    def test_cnbc_in_registry(self):
        from clawler.registry import get_entry
        entry = get_entry("cnbc")
        assert entry is not None
        assert entry.display_name == "CNBC"

    def test_marketwatch_in_registry(self):
        from clawler.registry import get_entry
        entry = get_entry("marketwatch")
        assert entry is not None
        assert entry.display_name == "MarketWatch"

    def test_total_sources_50(self):
        from clawler.registry import SOURCES
        assert len(SOURCES) == 52
