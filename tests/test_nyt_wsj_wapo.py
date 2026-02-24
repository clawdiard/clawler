"""Tests for NYT, WSJ, and Washington Post sources."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.nytimes import NYTimesSource, NYT_FEEDS
from clawler.sources.wsj import WSJSource, WSJ_FEEDS
from clawler.sources.washingtonpost import WashingtonPostSource, WAPO_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Test Feed</title>
  <item>
    <title>Test Article One</title>
    <link>https://example.com/article1</link>
    <description>Summary of article one.</description>
    <pubDate>Wed, 18 Feb 2026 12:00:00 GMT</pubDate>
    <author>Jane Doe</author>
  </item>
  <item>
    <title>Test Article Two</title>
    <link>https://example.com/article2</link>
    <description>Summary of article two with some longer text that goes on.</description>
    <pubDate>Wed, 18 Feb 2026 11:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


class TestNYTimesSource:
    def test_init_defaults(self):
        src = NYTimesSource()
        assert src.name == "nytimes"
        assert src.sections is None
        assert src.limit == 15

    def test_init_sections(self):
        src = NYTimesSource(sections=["World", "Tech"])
        assert src.sections == ["world", "tech"]

    def test_feed_config(self):
        assert len(NYT_FEEDS) >= 10
        for f in NYT_FEEDS:
            assert "url" in f and "section" in f and "category" in f

    @patch.object(NYTimesSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_parses_articles(self, mock_fetch):
        src = NYTimesSource(sections=["home"])
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Test Article One"
        assert articles[0].source.startswith("NYT")
        assert articles[0].url == "https://example.com/article1"
        assert "nytimes:" in articles[0].tags[0]

    @patch.object(NYTimesSource, "fetch_url", return_value="")
    def test_crawl_empty_feed(self, mock_fetch):
        src = NYTimesSource(sections=["home"])
        articles = src.crawl()
        assert articles == []


class TestWSJSource:
    def test_init_defaults(self):
        src = WSJSource()
        assert src.name == "wsj"

    def test_feed_config(self):
        assert len(WSJ_FEEDS) >= 5
        for f in WSJ_FEEDS:
            assert "url" in f and "section" in f and "category" in f

    @patch.object(WSJSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_parses_articles(self, mock_fetch):
        src = WSJSource(sections=["world"])
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].source.startswith("WSJ")

    @patch.object(WSJSource, "fetch_url", return_value="")
    def test_crawl_empty_feed(self, mock_fetch):
        src = WSJSource(sections=["world"])
        assert src.crawl() == []


class TestWashingtonPostSource:
    def test_init_defaults(self):
        src = WashingtonPostSource()
        assert src.name == "washingtonpost"

    def test_feed_config(self):
        assert len(WAPO_FEEDS) >= 5
        for key, f in WAPO_FEEDS.items():
            assert "url" in f and "label" in f and "fallback_cat" in f

    @patch.object(WashingtonPostSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_parses_articles(self, mock_fetch):
        src = WashingtonPostSource(sections=["national"])
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].source.startswith("WaPo")

    @patch.object(WashingtonPostSource, "fetch_url", return_value="")
    def test_crawl_empty_feed(self, mock_fetch):
        src = WashingtonPostSource(sections=["national"])
        assert src.crawl() == []


class TestRegistryInclusion:
    def test_new_sources_in_registry(self):
        from clawler.registry import SOURCES, get_entry
        keys = [s.key for s in SOURCES]
        assert "nytimes" in keys
        assert "wsj" in keys
        assert "washingtonpost" in keys
        # Can load classes
        for key in ("nytimes", "wsj", "washingtonpost"):
            entry = get_entry(key)
            cls = entry.load_class()
            assert cls is not None
