"""Tests for DZone source."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.dzone import DZoneSource, DZONE_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>DZone AI</title>
<item>
<title><![CDATA[Building LLM Agents with Tool Use]]></title>
<link>https://dzone.com/articles/building-llm-agents</link>
<description><![CDATA[A guide to building production-ready LLM agents.]]></description>
<pubDate>Mon, 16 Feb 2026 00:00:00 GMT</pubDate>
<dc:creator><![CDATA[Jane Developer]]></dc:creator>
<category><![CDATA[AI]]></category>
<category><![CDATA[LLM]]></category>
</item>
<item>
<title>Kubernetes Best Practices 2026</title>
<link>https://dzone.com/articles/k8s-best-practices</link>
<description>Updated Kubernetes patterns for cloud-native apps.</description>
<pubDate>Sun, 15 Feb 2026 12:00:00 GMT</pubDate>
<dc:creator>John Ops</dc:creator>
</item>
</channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0"?><rss><channel></channel></rss>"""


class TestDZoneSource:
    def test_init_defaults(self):
        src = DZoneSource()
        assert src.name == "dzone"
        assert src.feeds == DZONE_FEEDS
        assert len(src.feeds) == 12

    def test_init_custom_feeds(self):
        custom = [{"url": "https://example.com/rss", "topic": "test"}]
        src = DZoneSource(feeds=custom)
        assert src.feeds == custom

    @patch.object(DZoneSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_parses_articles(self, mock_fetch):
        src = DZoneSource(feeds=[{"url": "https://feeds.dzone.com/ai", "topic": "ai"}])
        articles = src.crawl()
        assert len(articles) == 2

        a = articles[0]
        assert a.title == "Building LLM Agents with Tool Use"
        assert a.url == "https://dzone.com/articles/building-llm-agents"
        assert a.author == "Jane Developer"
        assert a.source == "DZone (ai)"
        assert a.category == "tech"
        assert "dzone:ai" in a.tags
        assert "dzone:ai" in a.tags
        assert "dzone:llm" in a.tags
        assert a.timestamp is not None

        b = articles[1]
        assert b.title == "Kubernetes Best Practices 2026"
        assert b.author == "John Ops"

    @patch.object(DZoneSource, "fetch_url", return_value="")
    def test_crawl_empty_response(self, mock_fetch):
        src = DZoneSource(feeds=[{"url": "https://feeds.dzone.com/ai", "topic": "ai"}])
        articles = src.crawl()
        assert articles == []

    @patch.object(DZoneSource, "fetch_url", return_value=EMPTY_RSS)
    def test_crawl_no_items(self, mock_fetch):
        src = DZoneSource(feeds=[{"url": "https://feeds.dzone.com/ai", "topic": "ai"}])
        articles = src.crawl()
        assert articles == []

    @patch.object(DZoneSource, "fetch_url", side_effect=Exception("Network error"))
    def test_crawl_handles_errors(self, mock_fetch):
        src = DZoneSource(feeds=[{"url": "https://feeds.dzone.com/ai", "topic": "ai"}])
        articles = src.crawl()
        assert articles == []

    def test_security_topic_category(self):
        """Security topic should map to 'security' category."""
        src = DZoneSource(feeds=[{"url": "https://feeds.dzone.com/security", "topic": "security"}])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
            assert articles[0].category == "security"

    def test_limit_respected(self):
        src = DZoneSource(limit=1, feeds=[{"url": "https://feeds.dzone.com/ai", "topic": "ai"}])
        with patch.object(src, "fetch_url", return_value=SAMPLE_RSS):
            articles = src.crawl()
            assert len(articles) == 1
