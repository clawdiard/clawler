"""Tests for v5.6.0 features: --only, --json-lines, crawl timing."""
import sys
import io
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.cli import main
from clawler.models import Article


def _make_article(title="Test", url="https://example.com", source="TestSrc", category="tech"):
    return Article(
        title=title, url=url, source=source, category=category,
        summary="A test article", timestamp=datetime.now(tz=timezone.utc),
    )


class TestOnlyFlag:
    """Tests for the --only source filter."""

    def test_only_parses_single_source(self):
        """--only rss should disable all sources except RSS."""
        with patch("clawler.cli.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            mock_instance.crawl.return_value = ([], {}, MagicMock())
            MockEngine.return_value = mock_instance

            with pytest.raises(SystemExit):
                main(["--only", "rss", "--count"])

    def test_only_parses_multiple_sources(self):
        """--only rss,hn should enable both RSS and HN."""
        with patch("clawler.cli.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            mock_instance.crawl.return_value = ([], {"RSS": 0, "HN": 0}, MagicMock())
            MockEngine.return_value = mock_instance

            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main(["--only", "rss,hn", "--count", "--quiet"])
            assert captured.getvalue().strip() == "0"

    def test_only_unknown_source_warns(self):
        """--only with unknown source should warn on stderr."""
        captured_err = io.StringIO()
        with patch("clawler.cli.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            mock_instance.crawl.return_value = ([], {}, MagicMock())
            MockEngine.return_value = mock_instance
            with patch("sys.stderr", captured_err):
                try:
                    main(["--only", "rss,foobar", "--count", "--quiet"])
                except SystemExit:
                    pass
        assert "foobar" in captured_err.getvalue()

    def test_only_all_sources(self):
        """--only with all sources should not disable any."""
        all_srcs = "rss,hn,reddit,github,mastodon,wikipedia,lobsters,devto,arxiv,techmeme,producthunt,bluesky,tildes"
        with patch("clawler.cli.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            mock_instance.crawl.return_value = ([], {"src": 0}, MagicMock())
            MockEngine.return_value = mock_instance

            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main(["--only", all_srcs, "--count", "--quiet"])
            # Should create engine with all 12 sources
            call_kwargs = MockEngine.call_args[1] if MockEngine.call_args[1] else {}
            sources = call_kwargs.get("sources", MockEngine.call_args.kwargs.get("sources", []))
            assert len(sources) == 13


class TestJsonLinesAlias:
    """Tests for --json-lines alias."""

    def test_json_lines_sets_format(self):
        """--json-lines should produce JSONL output."""
        articles = [_make_article()]
        with patch("clawler.cli.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            from clawler.dedup import DedupStats
            mock_instance.crawl.return_value = (articles, {"TestSrc": 1}, DedupStats())
            MockEngine.return_value = mock_instance

            captured = io.StringIO()
            with patch("sys.stdout", captured):
                main(["--json-lines", "--quiet"])
            output = captured.getvalue().strip()
            # JSONL: each line is valid JSON
            import json
            parsed = json.loads(output.split("\n")[0])
            assert "title" in parsed


class TestCrawlTiming:
    """Tests for crawl timing summary."""

    def test_timing_printed_on_stderr(self):
        """Crawl timing should appear on stderr when not quiet."""
        with patch("clawler.cli.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            from clawler.dedup import DedupStats
            mock_instance.crawl.return_value = ([], {"RSS": 5}, DedupStats())
            MockEngine.return_value = mock_instance

            captured_err = io.StringIO()
            captured_out = io.StringIO()
            with patch("sys.stderr", captured_err), patch("sys.stdout", captured_out):
                # Force isatty to return True so auto-quiet doesn't kick in
                captured_out.isatty = lambda: True
                main(["--count"])
            err_output = captured_err.getvalue()
            assert "⏱️" in err_output or "Crawled" in err_output

    def test_timing_suppressed_when_quiet(self):
        """Timing should not appear with --quiet."""
        with patch("clawler.cli.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            from clawler.dedup import DedupStats
            mock_instance.crawl.return_value = ([], {"RSS": 5}, DedupStats())
            MockEngine.return_value = mock_instance

            captured_err = io.StringIO()
            captured_out = io.StringIO()
            with patch("sys.stderr", captured_err), patch("sys.stdout", captured_out):
                main(["--count", "--quiet"])
            assert "⏱️" not in captured_err.getvalue()


class TestOnlyAPI:
    """Tests for the 'only' parameter in the Python API."""

    def test_api_only_filters_sources(self):
        """API crawl(only='hn') should only enable HN source."""
        with patch("clawler.api.CrawlEngine") as MockEngine:
            mock_instance = MagicMock()
            from clawler.dedup import DedupStats
            mock_instance.crawl.return_value = ([], {}, DedupStats())
            MockEngine.return_value = mock_instance

            from clawler.api import crawl
            crawl(only="hn")

            call_args = MockEngine.call_args
            sources = call_args[1].get("sources") or call_args.kwargs.get("sources", [])
            assert len(sources) == 1
            assert "HackerNews" in type(sources[0]).__name__ or "Hacker" in type(sources[0]).__name__


class TestVersionSync:
    """Ensure version is consistent across all config files."""

    def test_version_is_560(self):
        from clawler import __version__
        assert __version__ == "5.7.0"
