"""Tests for Flipboard source."""
from unittest.mock import patch, MagicMock
from clawler.sources.flipboard import FlipboardSource, _quality_score, FLIPBOARD_TOPICS


class TestFlipboardTopics:
    def test_default_topics_count(self):
        assert len(FLIPBOARD_TOPICS) >= 10

    def test_all_topics_have_required_keys(self):
        for t in FLIPBOARD_TOPICS:
            assert "slug" in t
            assert "label" in t
            assert "category" in t


class TestQualityScore:
    def test_short_summary(self):
        score = _quality_score({"summary": "Short."})
        assert 0.4 <= score <= 0.55

    def test_long_summary(self):
        score = _quality_score({"summary": "x" * 250})
        assert score >= 0.55

    def test_empty_summary(self):
        score = _quality_score({})
        assert score == 0.45


class TestFlipboardSource:
    def test_name(self):
        src = FlipboardSource()
        assert src.name == "flipboard"

    def test_topic_filter(self):
        src = FlipboardSource(topics=["science"])
        # Only science topic should be selected in crawl
        assert src.topics == ["science"]

    @patch.object(FlipboardSource, "fetch_url", return_value="")
    def test_empty_feed(self, mock_fetch):
        src = FlipboardSource(topics=["technology"])
        articles = src.crawl()
        assert articles == []

    @patch.object(FlipboardSource, "fetch_url")
    def test_parse_rss(self, mock_fetch):
        mock_fetch.return_value = """<?xml version="1.0"?>
        <rss version="2.0">
        <channel>
          <item>
            <title>Test Article</title>
            <link>https://example.com/test</link>
            <description>A test article about tech.</description>
            <pubDate>Mon, 17 Feb 2026 08:00:00 GMT</pubDate>
          </item>
        </channel>
        </rss>"""
        src = FlipboardSource(topics=["technology"])
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        assert articles[0].url == "https://example.com/test"
        assert "flipboard:technology" in articles[0].tags
        assert articles[0].source == "Flipboard (Technology)"
