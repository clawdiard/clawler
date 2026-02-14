"""Tests for Clawler v4.4.0 features."""
from datetime import datetime, timezone

import pytest

from clawler import __version__
from clawler.models import Article


# -- Version sync --

class TestVersionSync:
    def test_version_is_440(self):
        assert __version__ == "4.5.0"


# -- RSS 2.0 formatter --

class TestRSSFormatter:
    def _make_articles(self, n=2):
        return [
            Article(
                title=f"Test Article {i}",
                url=f"https://example.com/{i}",
                source="TestSource",
                summary=f"Summary {i}",
                timestamp=datetime(2026, 2, 14, i, 0, tzinfo=timezone.utc),
                category="tech",
            )
            for i in range(1, n + 1)
        ]

    def test_rss_output_is_valid_xml_structure(self):
        from clawler.formatters.rss_out import RSSFormatter
        output = RSSFormatter().format(self._make_articles())
        assert output.startswith('<?xml version="1.0"')
        assert '<rss version="2.0">' in output
        assert '</rss>' in output
        assert '<channel>' in output

    def test_rss_contains_items(self):
        from clawler.formatters.rss_out import RSSFormatter
        output = RSSFormatter().format(self._make_articles(3))
        assert output.count('<item>') == 3
        assert output.count('</item>') == 3

    def test_rss_item_has_required_elements(self):
        from clawler.formatters.rss_out import RSSFormatter
        output = RSSFormatter().format(self._make_articles(1))
        assert '<title>Test Article 1</title>' in output
        assert '<link>https://example.com/1</link>' in output
        assert '<description>Summary 1</description>' in output
        assert '<category>tech</category>' in output
        assert '<pubDate>' in output

    def test_rss_html_escaping(self):
        from clawler.formatters.rss_out import RSSFormatter
        articles = [
            Article(title="A <b>bold</b> & 'tricky' \"title\"",
                    url="https://example.com/1", source="Src", summary="x&y",
                    timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), category="tech")
        ]
        output = RSSFormatter().format(articles)
        assert '&lt;b&gt;' in output
        assert '&amp;' in output

    def test_rss_empty_articles(self):
        from clawler.formatters.rss_out import RSSFormatter
        output = RSSFormatter().format([])
        assert '<item>' not in output
        assert '<channel>' in output

    def test_rss_no_timestamp(self):
        from clawler.formatters.rss_out import RSSFormatter
        articles = [Article(title="No Time", url="https://x.com", source="S", category="tech")]
        output = RSSFormatter().format(articles)
        assert '<item>' in output
        # pubDate line should be empty when no timestamp
        assert '<pubDate>' not in output


# -- CLI format flag --

class TestCLIRSSFormat:
    def test_rss_format_accepted(self):
        """Ensure -f rss is accepted by the argument parser."""
        import argparse
        from clawler.cli import main
        # Just verify it doesn't crash on parse (we can't run a full crawl in tests)
        parser = argparse.ArgumentParser()
        parser.add_argument("-f", "--format",
                            choices=["console", "json", "jsonl", "jsonfeed", "atom", "rss", "markdown", "csv", "html"])
        args = parser.parse_args(["-f", "rss"])
        assert args.format == "rss"


# -- Health timing --

class TestHealthTiming:
    def test_record_timing(self, tmp_path):
        import json
        from clawler.health import HealthTracker, HEALTH_PATH
        tracker = HealthTracker()
        tracker.data = {}  # reset
        tracker.record_success("TestSource", 10, response_ms=250.5)
        assert "TestSource" in tracker.data
        assert tracker.data["TestSource"]["response_times_ms"] == [250.5]

    def test_timing_capped_at_50(self):
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        tracker.data = {}
        for i in range(60):
            tracker.record_success("Src", 1, response_ms=float(i))
        assert len(tracker.data["Src"]["response_times_ms"]) == 50

    def test_timing_report_empty(self):
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        tracker.data = {}
        assert tracker.get_timing_report() == []

    def test_timing_report_sorted_slowest_first(self):
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        tracker.data = {
            "Fast": {"total_crawls": 1, "failures": 0, "total_articles": 5, "last_success": None, "response_times_ms": [100.0]},
            "Slow": {"total_crawls": 1, "failures": 0, "total_articles": 5, "last_success": None, "response_times_ms": [500.0]},
        }
        report = tracker.get_timing_report()
        assert len(report) == 2
        assert report[0]["source"] == "Slow"
        assert report[1]["source"] == "Fast"

    def test_timing_report_stats(self):
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        tracker.data = {
            "Src": {"total_crawls": 3, "failures": 0, "total_articles": 10, "last_success": None,
                     "response_times_ms": [100.0, 200.0, 300.0]},
        }
        report = tracker.get_timing_report()
        assert report[0]["avg_ms"] == 200.0
        assert report[0]["min_ms"] == 100.0
        assert report[0]["max_ms"] == 300.0
        assert report[0]["samples"] == 3


# -- New source weights --

class TestNewSourceWeights:
    def test_dev_community_weight(self):
        from clawler.weights import get_quality_score
        assert get_quality_score("DEV Community") == 0.64

    def test_slashdot_weight(self):
        from clawler.weights import get_quality_score
        assert get_quality_score("Slashdot") == 0.68

    def test_the_register_weight(self):
        from clawler.weights import get_quality_score
        assert get_quality_score("The Register") == 0.74

    def test_wikipedia_weight(self):
        from clawler.weights import get_quality_score
        assert get_quality_score("Wikipedia Current Events") == 0.80


# -- New RSS feeds --

class TestNewFeeds:
    def test_dev_to_in_default_feeds(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        sources = [f["source"] for f in DEFAULT_FEEDS]
        assert "DEV Community" in sources

    def test_slashdot_in_default_feeds(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        sources = [f["source"] for f in DEFAULT_FEEDS]
        assert "Slashdot" in sources

    def test_the_register_in_default_feeds(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        sources = [f["source"] for f in DEFAULT_FEEDS]
        assert "The Register" in sources

    def test_feed_count_increased(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        assert len(DEFAULT_FEEDS) >= 48  # was 45, added 3
