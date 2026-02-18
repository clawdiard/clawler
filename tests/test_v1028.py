"""Tests for Rest of World + Semafor sources (v10.28.0)."""
from unittest.mock import patch, MagicMock
from clawler.sources.restofworld import RestOfWorldSource
from clawler.sources.semafor import SemaforSource


FAKE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Test Feed</title>
<item>
  <title>Test Article About AI in Africa</title>
  <link>https://example.com/article-1</link>
  <description>AI is transforming industries across Africa.</description>
  <pubDate>Tue, 18 Feb 2026 12:00:00 +0000</pubDate>
  <author>Test Author</author>
</item>
<item>
  <title>Cybersecurity Breach in Southeast Asia</title>
  <link>https://example.com/article-2</link>
  <description>A major hack exposed millions of records.</description>
  <pubDate>Tue, 18 Feb 2026 11:00:00 +0000</pubDate>
</item>
</channel>
</rss>"""


class TestRestOfWorld:
    def test_crawl_parses_articles(self):
        src = RestOfWorldSource()
        with patch.object(src, "fetch_url", return_value=FAKE_RSS):
            articles = src.crawl()
        assert len(articles) >= 2
        assert articles[0].source.startswith("Rest of World")
        assert articles[0].quality_score == 0.82

    def test_crawl_keyword_refinement(self):
        src = RestOfWorldSource()
        with patch.object(src, "fetch_url", return_value=FAKE_RSS):
            articles = src.crawl()
        # The cybersecurity article should be refined to "security"
        cyber_articles = [a for a in articles if "hack" in a.summary.lower()]
        assert any(a.category == "security" for a in cyber_articles)

    def test_section_filter(self):
        src = RestOfWorldSource(sections=["Latest"])
        with patch.object(src, "fetch_url", return_value=FAKE_RSS):
            articles = src.crawl()
        assert all("Latest" in a.source for a in articles)

    def test_empty_feed(self):
        src = RestOfWorldSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []


class TestSemafor:
    def test_crawl_parses_articles(self):
        src = SemaforSource()
        with patch.object(src, "fetch_url", return_value=FAKE_RSS):
            articles = src.crawl()
        assert len(articles) >= 2
        assert articles[0].source.startswith("Semafor")
        assert articles[0].quality_score == 0.80

    def test_section_filter(self):
        src = SemaforSource(sections=["Tech"])
        with patch.object(src, "fetch_url", return_value=FAKE_RSS):
            articles = src.crawl()
        assert all("Tech" in a.source for a in articles)

    def test_empty_feed(self):
        src = SemaforSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_registry_includes_new_sources(self):
        from clawler.registry import get_all_keys
        keys = get_all_keys()
        assert "restofworld" in keys
        assert "semafor" in keys
