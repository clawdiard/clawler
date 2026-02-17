"""Tests for VentureBeat and TechRadar sources."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.venturebeat import VentureBeatSource
from clawler.sources.techradar import TechRadarSource


VENTUREBEAT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <title>VentureBeat</title>
  <item>
    <title>OpenAI launches new reasoning model</title>
    <link>https://venturebeat.com/ai/openai-reasoning-model/</link>
    <description>OpenAI has released a new AI reasoning model.</description>
    <dc:creator>Jane Doe</dc:creator>
    <pubDate>Mon, 17 Feb 2026 12:00:00 +0000</pubDate>
    <category>AI</category>
  </item>
  <item>
    <title>Startup raises $50M Series B for cloud security</title>
    <link>https://venturebeat.com/security/startup-series-b/</link>
    <description>A cybersecurity startup has raised a major round.</description>
    <pubDate>Mon, 17 Feb 2026 10:00:00 +0000</pubDate>
    <category>Security</category>
  </item>
</channel>
</rss>"""

TECHRADAR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
  <title>TechRadar</title>
  <item>
    <title>Best laptops 2026: our top picks</title>
    <link>https://www.techradar.com/best/best-laptops</link>
    <description>We tested dozens of laptops to find the best.</description>
    <dc:creator>John Smith</dc:creator>
    <pubDate>Mon, 17 Feb 2026 08:00:00 +0000</pubDate>
    <category>Computing</category>
  </item>
  <item>
    <title>iPhone 18 leak reveals major AI features</title>
    <link>https://www.techradar.com/phones/iphone-18-ai</link>
    <description>Apple is reportedly adding powerful AI capabilities.</description>
    <pubDate>Mon, 17 Feb 2026 06:00:00 +0000</pubDate>
    <category>Phones</category>
  </item>
</channel>
</rss>"""


class TestVentureBeat:
    def test_parse_articles(self):
        src = VentureBeatSource()
        with patch.object(src, 'fetch_url', return_value=VENTUREBEAT_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "OpenAI launches new reasoning model"
        assert articles[0].source == "VentureBeat"
        assert articles[0].category == "ai"
        assert articles[0].author == "Jane Doe"
        assert "vb:ai" in articles[0].tags

    def test_second_article_categorization(self):
        src = VentureBeatSource()
        with patch.object(src, 'fetch_url', return_value=VENTUREBEAT_RSS):
            articles = src.crawl()
        # "cloud security" matches security but title also has "cyber" context
        assert articles[1].category in ("security", "business", "ai")

    def test_empty_feed(self):
        src = VentureBeatSource()
        with patch.object(src, 'fetch_url', return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_name(self):
        assert VentureBeatSource.name == "venturebeat"

    def test_dedup_urls(self):
        """Duplicate URLs should be skipped."""
        # Create RSS with two items sharing the same URL
        dupe_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>VB</title>
  <item>
    <title>Article One</title>
    <link>https://venturebeat.com/same-url/</link>
    <pubDate>Mon, 17 Feb 2026 12:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Article Two</title>
    <link>https://venturebeat.com/same-url/</link>
    <pubDate>Mon, 17 Feb 2026 10:00:00 +0000</pubDate>
  </item>
</channel></rss>"""
        src = VentureBeatSource()
        with patch.object(src, 'fetch_url', return_value=dupe_rss):
            articles = src.crawl()
        assert len(articles) == 1


class TestTechRadar:
    def test_parse_articles(self):
        src = TechRadarSource()
        with patch.object(src, 'fetch_url', return_value=TECHRADAR_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Best laptops 2026: our top picks"
        assert articles[0].source == "TechRadar"

    def test_ai_categorization(self):
        src = TechRadarSource()
        with patch.object(src, 'fetch_url', return_value=TECHRADAR_RSS):
            articles = src.crawl()
        # iPhone 18 with AI features should be categorized as AI
        assert articles[1].category == "ai"

    def test_empty_feed(self):
        src = TechRadarSource()
        with patch.object(src, 'fetch_url', return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_name(self):
        assert TechRadarSource.name == "techradar"

    def test_multi_feed(self):
        """Should fetch from multiple feeds and deduplicate."""
        src = TechRadarSource()
        call_count = 0
        def mock_fetch(url):
            nonlocal call_count
            call_count += 1
            return TECHRADAR_RSS
        with patch.object(src, 'fetch_url', side_effect=mock_fetch):
            articles = src.crawl()
        # 3 feeds but same URLs → deduped to 2
        assert call_count == 3
        assert len(articles) == 2
