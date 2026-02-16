"""Tests for Nature source."""
import pytest
from unittest.mock import patch
from clawler.sources.nature import NatureSource, NATURE_FEEDS

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Nature</title>
<item>
  <title>CRISPR gene editing shows promise for treating rare diseases</title>
  <link>https://www.nature.com/articles/d41586-026-00001-1</link>
  <description>A new study demonstrates CRISPR-based therapies can target previously untreatable conditions.</description>
  <pubDate>Sat, 14 Feb 2026 10:00:00 GMT</pubDate>
  <dc:creator><![CDATA[Jane Smith]]></dc:creator>
</item>
<item>
  <title>AI models predict protein folding with unprecedented accuracy</title>
  <link>https://www.nature.com/articles/d41586-026-00002-2</link>
  <description>Machine learning advances push protein structure prediction to near-experimental accuracy.</description>
  <pubDate>Fri, 13 Feb 2026 08:00:00 GMT</pubDate>
</item>
</channel>
</rss>"""


class TestNatureSource:
    def test_feed_config(self):
        assert len(NATURE_FEEDS) == 5
        sections = {f["section"] for f in NATURE_FEEDS}
        assert "nature" in sections
        assert "machine-intelligence" in sections

    def test_source_name(self):
        src = NatureSource()
        assert src.name == "nature"

    @patch.object(NatureSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_parse_articles(self, mock_fetch):
        src = NatureSource(feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature"}])
        articles = src.crawl()
        assert len(articles) == 2
        assert "CRISPR" in articles[0].title
        assert articles[0].source == "Nature (nature)"
        assert articles[0].category == "science"
        assert articles[0].author == "Jane Smith"
        assert articles[0].timestamp is not None
        assert "nature:nature" in articles[0].tags

    @patch.object(NatureSource, "fetch_url", return_value="")
    def test_empty_feed(self, mock_fetch):
        src = NatureSource(feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature"}])
        articles = src.crawl()
        assert articles == []

    @patch.object(NatureSource, "fetch_url", side_effect=Exception("Network error"))
    def test_fetch_failure(self, mock_fetch):
        src = NatureSource(feeds=[{"url": "https://www.nature.com/nature.rss", "section": "nature"}])
        articles = src.crawl()
        assert articles == []

    def test_limit(self):
        src = NatureSource(limit=10)
        assert src.limit == 10


class TestNatureIntegration:
    def test_import(self):
        from clawler.sources import NatureSource as NS
        assert NS is not None
