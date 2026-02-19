"""Tests for NPR source."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.npr import NPRSource, NPR_FEEDS


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>NPR News</title>
  <item>
    <title>Test Article One</title>
    <link>https://www.npr.org/2026/02/16/article-one</link>
    <description>Summary of article one.</description>
    <pubDate>Sun, 16 Feb 2026 01:00:00 -0500</pubDate>
    <author>Jane Doe</author>
  </item>
  <item>
    <title>Test Article Two</title>
    <link>https://www.npr.org/2026/02/16/article-two</link>
    <description>Summary of article two with &lt;b&gt;HTML&lt;/b&gt; tags.</description>
    <pubDate>Sun, 16 Feb 2026 00:30:00 -0500</pubDate>
  </item>
</channel>
</rss>"""


class TestNPRSource:
    def test_feeds_config(self):
        """NPR_FEEDS should have 10 section feeds."""
        assert len(NPR_FEEDS) == 18
        sections = {f["section"] for f in NPR_FEEDS}
        assert "News" in sections
        assert "Technology" in sections
        assert "Science" in sections

    def test_init_defaults(self):
        src = NPRSource()
        assert src.name == "npr"
        assert src.sections is None
        assert src.limit == 15

    def test_init_sections_filter(self):
        src = NPRSource(sections=["Science", "Tech"])
        assert src.sections == ["science", "tech"]

    @patch.object(NPRSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_crawl_parses_articles(self, mock_fetch):
        src = NPRSource(sections=["News"])
        articles = src.crawl()
        assert len(articles) == 2
        assert articles[0].title == "Test Article One"
        assert articles[0].source == "NPR (News)"
        assert articles[0].category == "culture"
        assert articles[0].url == "https://www.npr.org/2026/02/16/article-one"
        assert articles[0].timestamp is not None
        assert "npr:section:news" in articles[0].tags

    @patch.object(NPRSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_html_stripped_from_summary(self, mock_fetch):
        src = NPRSource(sections=["News"])
        articles = src.crawl()
        # Second article has HTML in description
        assert "<b>" not in articles[1].summary
        assert "HTML" in articles[1].summary

    @patch.object(NPRSource, "fetch_url", return_value="")
    def test_empty_feed_returns_empty(self, mock_fetch):
        src = NPRSource(sections=["News"])
        articles = src.crawl()
        assert articles == []

    @patch.object(NPRSource, "fetch_url", return_value=SAMPLE_RSS)
    def test_limit_respected(self, mock_fetch):
        src = NPRSource(sections=["News"], limit=1)
        articles = src.crawl()
        assert len(articles) == 1

    def test_all_feeds_have_required_keys(self):
        for feed in NPR_FEEDS:
            assert "url" in feed
            assert "section" in feed
            assert "category" in feed
            assert feed["url"].startswith("https://feeds.npr.org/")

    @patch.object(NPRSource, "fetch_url", side_effect=Exception("Network error"))
    def test_crawl_handles_errors_gracefully(self, mock_fetch):
        src = NPRSource(sections=["News"])
        articles = src.crawl()
        assert articles == []


class TestNPRIntegration:
    def test_source_in_init(self):
        """NPRSource should be importable from the sources package."""
        from clawler.sources import NPRSource as Imported
        assert Imported is NPRSource

    def test_weights_exist(self):
        """NPR sources should have quality weights."""
        from clawler.weights import get_quality_score
        score = get_quality_score("NPR (News)")
        assert score > 0.5  # Should have a real weight, not default
