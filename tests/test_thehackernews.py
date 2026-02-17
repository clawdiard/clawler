"""Tests for The Hacker News (cybersecurity) source."""
import pytest
from unittest.mock import patch
from clawler.sources.thehackernews import TheHackerNewsSource, _classify_security_topic

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>The Hacker News</title>
    <item>
      <title>Critical Zero-Day Vulnerability Found in Popular Router Firmware</title>
      <link>https://thehackernews.com/2026/02/zero-day-router.html</link>
      <pubDate>Mon, 16 Feb 2026 10:00:00 GMT</pubDate>
      <author>Ravie Lakshmanan</author>
      <description>&lt;p&gt;Security researchers have discovered a critical zero-day vulnerability affecting millions of routers.&lt;/p&gt;</description>
      <category>Vulnerability</category>
      <category>IoT Security</category>
    </item>
    <item>
      <title>New Ransomware Gang Targets Healthcare Sector</title>
      <link>https://thehackernews.com/2026/02/ransomware-healthcare.html</link>
      <pubDate>Sun, 15 Feb 2026 14:00:00 GMT</pubDate>
      <description>&lt;p&gt;A new ransomware operation has been observed targeting hospitals and medical facilities.&lt;/p&gt;</description>
    </item>
    <item>
      <title></title>
      <link></link>
    </item>
  </channel>
</rss>"""


class TestClassifySecurityTopic:
    def test_vulnerability(self):
        tags = _classify_security_topic("Critical Zero-Day Found", "a new vulnerability exploit")
        assert "vulnerability" in tags

    def test_malware(self):
        tags = _classify_security_topic("New Ransomware Targets Banks", "malware campaign")
        assert "malware" in tags

    def test_breach(self):
        tags = _classify_security_topic("Major Data Breach Exposes Millions", "credentials stolen")
        assert "breach" in tags

    def test_neutral(self):
        tags = _classify_security_topic("Google Launches New Security Tool", "a new product")
        assert tags == []


class TestTheHackerNewsSource:
    def test_defaults(self):
        src = TheHackerNewsSource()
        assert src.name == "thehackernews"
        assert src.limit == 25

    def test_custom_limit(self):
        src = TheHackerNewsSource(limit=10)
        assert src.limit == 10

    @patch.object(TheHackerNewsSource, "fetch_url")
    def test_crawl(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = TheHackerNewsSource()
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Critical Zero-Day Vulnerability Found in Popular Router Firmware"
        assert articles[0].source == "The Hacker News"
        assert articles[0].category == "security"
        assert articles[0].timestamp is not None
        assert articles[0].author == "Ravie Lakshmanan"
        assert "cybersecurity" in articles[0].tags
        assert "vulnerability" in articles[0].tags  # from classifier
        assert articles[1].title == "New Ransomware Gang Targets Healthcare Sector"
        assert "malware" in articles[1].tags

    @patch.object(TheHackerNewsSource, "fetch_url")
    def test_crawl_empty(self, mock_fetch):
        mock_fetch.return_value = ""
        src = TheHackerNewsSource()
        assert src.crawl() == []

    @patch.object(TheHackerNewsSource, "fetch_url")
    def test_crawl_limit(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = TheHackerNewsSource(limit=1)
        articles = src.crawl()
        assert len(articles) == 1

    @patch.object(TheHackerNewsSource, "fetch_url")
    def test_feed_tags_included(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = TheHackerNewsSource()
        articles = src.crawl()
        # First article has <category> tags from feed
        assert "iot security" in articles[0].tags
