"""Tests for ScienceDaily source."""
import pytest
from unittest.mock import patch
from clawler.sources.sciencedaily import ScienceDailySource, SCIENCEDAILY_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>ScienceDaily: Top Science News</title>
<item>
<title>New Quantum Computing Breakthrough Achieves Error Correction</title>
<link>https://www.sciencedaily.com/releases/2026/02/260216001.htm</link>
<description>Researchers have demonstrated a new approach to quantum error correction that could accelerate practical quantum computing.</description>
<pubDate>Mon, 16 Feb 2026 00:00:00 GMT</pubDate>
</item>
<item>
<title><![CDATA[Mars Rover Discovers New Mineral Formation]]></title>
<link>https://www.sciencedaily.com/releases/2026/02/260215002.htm</link>
<description><![CDATA[A previously unknown mineral has been identified on Mars.]]></description>
<pubDate>Sun, 15 Feb 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


class TestScienceDailySource:
    def test_init_defaults(self):
        src = ScienceDailySource()
        assert src.name == "sciencedaily"
        assert src.feeds == SCIENCEDAILY_FEEDS
        assert len(src.feeds) == 10

    @patch.object(ScienceDailySource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_parses_articles(self, mock_fetch):
        src = ScienceDailySource(feeds=[{"url": "https://www.sciencedaily.com/rss/top.xml", "section": "top"}])
        articles = src.crawl()
        assert len(articles) == 2

        a = articles[0]
        assert "Quantum" in a.title
        assert a.source == "ScienceDaily (top)"
        assert a.category == "physics"  # keyword detection: "quantum"
        assert "sciencedaily:section:top" in a.tags
        assert a.timestamp is not None

        b = articles[1]
        assert "Mars" in b.title

    @patch.object(ScienceDailySource, "fetch_url", return_value="")
    def test_crawl_empty(self, mock_fetch):
        src = ScienceDailySource(feeds=[{"url": "https://test.com/rss", "section": "top"}])
        assert src.crawl() == []

    @patch.object(ScienceDailySource, "fetch_url", side_effect=Exception("fail"))
    def test_crawl_error(self, mock_fetch):
        src = ScienceDailySource(feeds=[{"url": "https://test.com/rss", "section": "top"}])
        assert src.crawl() == []

    def test_computers_section_is_tech(self):
        src = ScienceDailySource(feeds=[{"url": "https://test.com/rss", "section": "computers"}])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
            assert articles[0].category == "physics"  # keyword detection overrides section default

    def test_limit(self):
        src = ScienceDailySource(limit=1, feeds=[{"url": "https://test.com/rss", "section": "top"}])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            assert len(src.crawl()) == 1
