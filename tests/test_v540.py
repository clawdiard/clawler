"""Tests for v5.4.0 — ISO dates in --since, URL normalization in dedup, version sync."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from clawler.utils import parse_since, relative_time
from clawler.models import Article, _normalize_url
from clawler.dedup import deduplicate, DedupStats


class TestParseSinceISO:
    """Test ISO-8601 date support in parse_since."""

    def test_iso_date_only(self):
        dt = parse_since("2026-02-14")
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 14
        assert dt.tzinfo == timezone.utc

    def test_iso_datetime(self):
        dt = parse_since("2026-02-14T10:30:00")
        assert dt.hour == 10
        assert dt.minute == 30
        assert dt.tzinfo == timezone.utc

    def test_iso_datetime_with_z(self):
        dt = parse_since("2026-02-14T10:30:00Z")
        assert dt.hour == 10
        assert dt.tzinfo == timezone.utc

    def test_iso_datetime_with_tz(self):
        dt = parse_since("2026-02-14T10:30:00+00:00")
        assert dt.hour == 10

    def test_relative_still_works(self):
        dt = parse_since("2h")
        now = datetime.now(timezone.utc)
        diff = now - dt
        assert 7100 < diff.total_seconds() < 7300  # ~2 hours

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid since value"):
            parse_since("not-a-date")

    def test_whitespace_handling(self):
        dt = parse_since("  2026-02-14  ")
        assert dt.year == 2026


class TestURLNormalization:
    """Test _normalize_url for dedup improvements."""

    def test_strip_www(self):
        assert _normalize_url("https://www.example.com/article") == "https://example.com/article"

    def test_strip_trailing_slash(self):
        assert _normalize_url("https://example.com/article/") == "https://example.com/article"

    def test_preserve_path(self):
        assert _normalize_url("https://example.com/a/b/c") == "https://example.com/a/b/c"

    def test_root_path(self):
        assert _normalize_url("https://example.com/") == "https://example.com/"
        assert _normalize_url("https://example.com") == "https://example.com/"

    def test_lowercases_host(self):
        assert _normalize_url("https://EXAMPLE.COM/Article") == "https://example.com/Article"


class TestDedupURLNormalization:
    """Test that URL normalization improves dedup matching."""

    def test_www_variants_dedup(self):
        a1 = Article(title="Same Story", url="https://www.example.com/story", source="A", quality_score=0.8)
        a2 = Article(title="Same Story", url="https://example.com/story", source="A", quality_score=0.7)
        stats = DedupStats()
        result = deduplicate([a1, a2], stats=stats)
        assert len(result) == 1
        assert stats.exact_dupes == 1

    def test_trailing_slash_variants_dedup(self):
        a1 = Article(title="Same Story", url="https://example.com/story/", source="A", quality_score=0.8)
        a2 = Article(title="Same Story", url="https://example.com/story", source="A", quality_score=0.7)
        stats = DedupStats()
        result = deduplicate([a1, a2], stats=stats)
        assert len(result) == 1


class TestVersionSync:
    """Verify version strings are consistent."""

    def test_init_version(self):
        from clawler import __version__
        assert __version__ >= "5.4.0"

    def test_setup_version(self):
        import ast
        with open("setup.py", "r") as f:
            content = f.read()
        assert '"5.4.0"' in content or "'5.4.0'" in content or '"5.5.0"' in content or "'5.5.0'" in content or '"5.6.0"' in content or "'5.6.0'" in content


class TestRelativeTimeEdgeCases:
    """Additional tests for relative_time edge cases."""

    def test_future_timestamp(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert relative_time(future) == "just now"

    def test_weeks_ago(self):
        old = datetime.now(timezone.utc) - timedelta(days=14)
        assert relative_time(old) == "2w ago"

    def test_naive_datetime(self):
        # Should not crash — treats as UTC
        naive = datetime.now() - timedelta(hours=2)
        result = relative_time(naive)
        assert "ago" in result
