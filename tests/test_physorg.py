"""Tests for Phys.org source."""
import pytest
from unittest.mock import patch
from clawler.sources.physorg import PhysOrgSource, PHYSORG_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Phys.org - Breaking</title>
<item>
  <title>New quantum computing breakthrough achieves record qubit count</title>
  <link>https://phys.org/news/2026-02-quantum-computing.html</link>
  <description>Researchers have achieved a new milestone in quantum computing with 1000+ qubits.</description>
  <pubDate>Sun, 15 Feb 2026 14:00:00 GMT</pubDate>
</item>
<item>
  <title>Mars rover discovers ancient water signatures</title>
  <link>https://phys.org/news/2026-02-mars-rover.html</link>
  <description>The latest Mars mission has found compelling evidence of ancient water.</description>
  <pubDate>Sun, 15 Feb 2026 12:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


class TestPhysOrgSource:
    def test_feed_config(self):
        assert len(PHYSORG_FEEDS) == 11
        sections = {f["section"] for f in PHYSORG_FEEDS}
        assert "breaking" in sections
        assert "physics" in sections
        assert "space" in sections

    def test_source_name(self):
        src = PhysOrgSource()
        assert src.name == "physorg"

    @patch.object(PhysOrgSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_parse_articles(self, mock_fetch):
        src = PhysOrgSource(feeds=[{"url": "https://phys.org/rss-feed/breaking/", "section": "breaking"}])
        articles = src.crawl()
        assert len(articles) == 2
        assert "quantum" in articles[0].title.lower()
        assert articles[0].source == "Phys.org (breaking)"
        assert articles[0].category == "science"
        assert articles[0].timestamp is not None
        assert "physorg:breaking" in articles[0].tags

    @patch.object(PhysOrgSource, "fetch_url", return_value="")
    def test_empty_feed(self, mock_fetch):
        src = PhysOrgSource(feeds=[{"url": "https://phys.org/rss-feed/breaking/", "section": "breaking"}])
        articles = src.crawl()
        assert articles == []

    @patch.object(PhysOrgSource, "fetch_url", side_effect=Exception("Network error"))
    def test_fetch_failure(self, mock_fetch):
        src = PhysOrgSource(feeds=[{"url": "https://phys.org/rss-feed/breaking/", "section": "breaking"}])
        articles = src.crawl()
        assert articles == []

    def test_limit(self):
        src = PhysOrgSource(limit=5)
        assert src.limit == 5

    def test_custom_feeds(self):
        custom = [{"url": "https://phys.org/rss-feed/physics-news/", "section": "physics"}]
        src = PhysOrgSource(feeds=custom)
        assert len(src.feeds) == 1


class TestPhysOrgIntegration:
    def test_import(self):
        from clawler.sources import PhysOrgSource as PS
        assert PS is not None

    def test_engine_includes_physorg(self):
        from clawler.sources import PhysOrgSource
        src = PhysOrgSource()
        assert src.name == "physorg"
