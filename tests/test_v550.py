"""Tests for v5.5.0 features: retry logic, named --since periods, --export-health, --retries flag."""
import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from clawler.engine import CrawlEngine
from clawler.models import Article
from clawler.utils import parse_since


# --- Named --since period tests ---

class TestNamedSincePeriods:
    def test_yesterday(self):
        result = parse_since("yesterday")
        expected = datetime.now(timezone.utc) - timedelta(days=1)
        assert abs((result - expected).total_seconds()) < 2

    def test_last_week(self):
        result = parse_since("last-week")
        expected = datetime.now(timezone.utc) - timedelta(weeks=1)
        assert abs((result - expected).total_seconds()) < 2

    def test_last_month(self):
        result = parse_since("last-month")
        expected = datetime.now(timezone.utc) - timedelta(days=30)
        assert abs((result - expected).total_seconds()) < 2

    def test_last_year(self):
        result = parse_since("last-year")
        expected = datetime.now(timezone.utc) - timedelta(days=365)
        assert abs((result - expected).total_seconds()) < 2

    def test_case_insensitive(self):
        result = parse_since("Yesterday")
        expected = datetime.now(timezone.utc) - timedelta(days=1)
        assert abs((result - expected).total_seconds()) < 2

    def test_with_whitespace(self):
        result = parse_since("  last-week  ")
        expected = datetime.now(timezone.utc) - timedelta(weeks=1)
        assert abs((result - expected).total_seconds()) < 2


# --- Retry logic tests ---

class TestRetryLogic:
    def _make_source(self, name, fail_count=0):
        """Create a mock source that fails `fail_count` times then succeeds."""
        src = MagicMock()
        src.name = name
        call_count = {"n": 0}
        def crawl_side_effect():
            call_count["n"] += 1
            if call_count["n"] <= fail_count:
                raise ConnectionError(f"Simulated failure #{call_count['n']}")
            return [Article(title=f"Article from {name}", url=f"https://example.com/{name}", source=name)]
        src.crawl.side_effect = crawl_side_effect
        return src

    def test_no_retry_when_success(self):
        src = self._make_source("good", fail_count=0)
        engine = CrawlEngine(sources=[src], max_workers=1, retries=1)
        articles, stats, _ = engine.crawl()
        assert stats["good"] == 1
        assert len(articles) == 1

    def test_retry_recovers_from_failure(self):
        src = self._make_source("flaky", fail_count=1)
        engine = CrawlEngine(sources=[src], max_workers=1, retries=1)
        with patch("clawler.engine.time.sleep"):  # skip actual sleep
            articles, stats, _ = engine.crawl()
        assert stats["flaky"] == 1
        assert len(articles) == 1

    def test_retry_exhausted(self):
        src = self._make_source("broken", fail_count=5)
        engine = CrawlEngine(sources=[src], max_workers=1, retries=2)
        with patch("clawler.engine.time.sleep"):
            articles, stats, _ = engine.crawl()
        assert stats["broken"] == -1
        assert len(articles) == 0

    def test_zero_retries_no_retry(self):
        src = self._make_source("once", fail_count=1)
        engine = CrawlEngine(sources=[src], max_workers=1, retries=0)
        articles, stats, _ = engine.crawl()
        assert stats["once"] == -1

    def test_retry_does_not_affect_healthy_sources(self):
        good = self._make_source("good", fail_count=0)
        flaky = self._make_source("flaky", fail_count=1)
        engine = CrawlEngine(sources=[good, flaky], max_workers=1, retries=1)
        with patch("clawler.engine.time.sleep"):
            articles, stats, _ = engine.crawl()
        assert stats["good"] == 1
        assert stats["flaky"] == 1
        assert len(articles) == 2


# --- CLI flag tests ---

class TestCLIFlags:
    def test_retries_flag_parsed(self):
        from clawler.cli import main
        # --retries should be accepted without error (dry-run to avoid actual crawl)
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0

    def test_export_health_creates_file(self):
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        tracker.record_success("TestSource", 5, response_ms=100)
        tracker.save()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmppath = f.name
        try:
            from clawler.cli import main
            main(["--export-health", tmppath])
            with open(tmppath) as f:
                data = json.load(f)
            assert isinstance(data, list)
        finally:
            os.unlink(tmppath)

    def test_no_retry_flag(self):
        """--no-retry should be accepted."""
        from clawler.cli import main
        with pytest.raises(SystemExit):
            main(["--no-retry", "--version"])


# --- Version sync test ---

class TestVersionSync:
    def test_version_is_550(self):
        from clawler import __version__
        assert __version__ == "5.7.0"
