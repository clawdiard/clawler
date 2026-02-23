"""Tests for Vox and Salon sources."""
from unittest.mock import patch, MagicMock
from clawler.sources.vox import VoxSource
from clawler.sources.salon import SalonSource

MOCK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Test Feed</title>
  <item>
    <title>AI Revolution in Policy Making</title>
    <link>https://www.example.com/ai-policy</link>
    <description>A deep dive into how artificial intelligence is reshaping government.</description>
    <pubDate>Mon, 23 Feb 2026 12:00:00 GMT</pubDate>
    <author>Test Author</author>
  </item>
  <item>
    <title>Climate Change Update</title>
    <link>https://www.example.com/climate</link>
    <description>New research on climate models.</description>
    <pubDate>Mon, 23 Feb 2026 11:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


class TestVoxSource:
    def test_crawl_returns_articles(self):
        src = VoxSource(sections=["latest"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "AI Revolution in Policy Making"
        assert articles[0].source == "Vox (Latest)"
        assert "vox:latest" in articles[0].tags

    def test_section_filter(self):
        src = VoxSource(sections=["technology"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        # Only "Technology" section matched, "Latest" skipped
        assert len(articles) == 2

    def test_keyword_category_refinement(self):
        src = VoxSource(limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        # First article has "artificial intelligence" -> should refine to tech
        ai_article = [a for a in articles if "AI" in a.title][0]
        assert ai_article.category == "tech"

    def test_quality_boost_for_deep_dive(self):
        src = VoxSource(sections=["latest"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        deep_dive = [a for a in articles if "deep dive" in a.summary.lower()]
        assert len(deep_dive) == 1
        assert deep_dive[0].quality_score >= 0.85

    def test_empty_feed(self):
        src = VoxSource(limit=5)
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_name(self):
        assert VoxSource().name == "vox"


class TestSalonSource:
    def test_crawl_returns_articles(self):
        src = SalonSource(sections=["latest"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].source == "Salon (Latest)"
        assert "salon:latest" in articles[0].tags

    def test_empty_feed(self):
        src = SalonSource(limit=5)
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        assert articles == []

    def test_name(self):
        assert SalonSource().name == "salon"

    def test_keyword_category_refinement(self):
        src = SalonSource(sections=["latest"], limit=5)
        with patch.object(src, "fetch_url", return_value=MOCK_RSS):
            articles = src.crawl()
        climate = [a for a in articles if "Climate" in a.title][0]
        assert climate.category == "science"
