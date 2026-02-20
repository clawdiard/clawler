"""Tests for The Atlantic and CNET sources (v10.56.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.theatlantic import TheAtlanticSource, _detect_category, _parse_date
from clawler.sources.cnet import CNETSource


ATLANTIC_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>The Atlantic</title>
    <item>
      <title>The AI Revolution Is Changing Everything</title>
      <link>https://www.theatlantic.com/technology/archive/2026/02/ai-revolution/123456/</link>
      <description>Artificial intelligence is reshaping how we work and live.</description>
      <dc:creator>Derek Thompson</dc:creator>
      <pubDate>Thu, 20 Feb 2026 12:00:00 GMT</pubDate>
      <category>Technology</category>
    </item>
    <item>
      <title>The Future of Democracy in America</title>
      <link>https://www.theatlantic.com/politics/archive/2026/02/democracy-future/123457/</link>
      <description>An examination of democratic institutions under pressure.</description>
      <dc:creator>Anne Applebaum</dc:creator>
      <pubDate>Wed, 19 Feb 2026 10:00:00 GMT</pubDate>
      <category>Politics</category>
    </item>
  </channel>
</rss>"""


CNET_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>CNET News</title>
    <item>
      <title>Best Laptops for 2026: Our Top Picks</title>
      <link>https://www.cnet.com/tech/computing/best-laptops/</link>
      <description>We tested dozens of laptops to find the best ones for every budget.</description>
      <dc:creator>Josh Goldman</dc:creator>
      <pubDate>Thu, 20 Feb 2026 14:00:00 GMT</pubDate>
      <category>Computing</category>
    </item>
    <item>
      <title>New iPhone Security Flaw Discovered</title>
      <link>https://www.cnet.com/tech/mobile/iphone-security-flaw/</link>
      <description>A critical security vulnerability affects millions of iPhone users.</description>
      <pubDate>Wed, 19 Feb 2026 09:00:00 GMT</pubDate>
      <category>Mobile</category>
    </item>
  </channel>
</rss>"""


class TestTheAtlanticSource:
    def test_parse_articles(self):
        src = TheAtlanticSource(sections=["latest"])
        with patch.object(src, "fetch_url", return_value=ATLANTIC_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "The AI Revolution Is Changing Everything"
        assert articles[0].author == "Derek Thompson"
        assert "atlantic:latest" in articles[0].tags
        assert articles[0].source == "The Atlantic (Latest)"

    def test_dedup_across_sections(self):
        src = TheAtlanticSource(sections=["latest", "technology"])
        with patch.object(src, "fetch_url", return_value=ATLANTIC_RSS):
            articles = src.crawl()
        # Same URLs should be deduped across sections
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    def test_empty_feed(self):
        src = TheAtlanticSource(sections=["latest"])
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_invalid_xml(self):
        src = TheAtlanticSource(sections=["latest"])
        with patch.object(src, "fetch_url", return_value="<not valid xml"):
            articles = src.crawl()
        assert articles == []

    def test_category_detection(self):
        assert _detect_category("AI is transforming healthcare", "", "technology") == "tech"
        assert _detect_category("Ukraine war escalates amid diplomacy talks", "", "international") == "world"
        assert _detect_category("A quiet piece about life", "", "ideas") == "general"

    def test_parse_date(self):
        dt = _parse_date("Thu, 20 Feb 2026 12:00:00 GMT")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 2

    def test_parse_date_none(self):
        assert _parse_date(None) is None
        assert _parse_date("") is None


class TestCNETSource:
    def test_parse_articles(self):
        src = CNETSource(sections=["news"])
        with patch.object(src, "fetch_url", return_value=CNET_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].source == "CNET (News)"
        assert "cnet:news" in articles[0].tags

    def test_security_category(self):
        src = CNETSource(sections=["news"])
        with patch.object(src, "fetch_url", return_value=CNET_RSS):
            articles = src.crawl()
        # "iPhone" in title matches tech keywords first
        security_article = [a for a in articles if "security" in a.title.lower()][0]
        assert security_article.category in ("tech", "security")

    def test_empty_feed(self):
        src = CNETSource(sections=["news"])
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_limit(self):
        src = CNETSource(sections=["news"], limit=1)
        with patch.object(src, "fetch_url", return_value=CNET_RSS):
            articles = src.crawl()
        assert len(articles) <= 1


class TestRegistryIntegration:
    def test_new_sources_in_registry(self):
        from clawler.registry import get_entry, get_all_keys
        assert "theatlantic" in get_all_keys()
        assert "cnet" in get_all_keys()
        
        atlantic = get_entry("theatlantic")
        assert atlantic is not None
        assert atlantic.display_name == "The Atlantic"
        
        cnet = get_entry("cnet")
        assert cnet is not None
        assert cnet.display_name == "CNET"

    def test_source_classes_loadable(self):
        from clawler.registry import get_entry
        atlantic_cls = get_entry("theatlantic").load_class()
        assert atlantic_cls.__name__ == "TheAtlanticSource"
        
        cnet_cls = get_entry("cnet").load_class()
        assert cnet_cls.__name__ == "CNETSource"
