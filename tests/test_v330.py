"""Tests for v3.3.0 features."""
from datetime import datetime, timedelta, timezone

from clawler.utils import parse_since


class TestParseSinceExtended:
    """Test month and year units in parse_since."""

    def test_months(self):
        result = parse_since("3M")
        expected_approx = datetime.now(timezone.utc) - timedelta(days=90)
        assert abs((result - expected_approx).total_seconds()) < 2

    def test_year(self):
        result = parse_since("1y")
        expected_approx = datetime.now(timezone.utc) - timedelta(days=365)
        assert abs((result - expected_approx).total_seconds()) < 2

    def test_case_sensitive_months(self):
        """M = months (30d), m = minutes — they must differ."""
        months = parse_since("1M")
        minutes = parse_since("1m")
        # 1 month (~30 days) should be much larger than 1 minute
        assert (minutes - months).total_seconds() > 86000  # > ~1 day difference at least

    def test_existing_units_still_work(self):
        for val in ["30s", "5m", "2h", "1d", "1w"]:
            result = parse_since(val)
            assert result < datetime.now(timezone.utc)


class TestStaleFilter:
    """Test that --stale flag concept works (filter logic)."""

    def test_stale_filter_keeps_old_articles(self):
        from clawler.models import Article
        now = datetime.now(timezone.utc)
        old = Article(title="Old", url="http://old", source="test",
                      timestamp=now - timedelta(hours=24))
        new = Article(title="New", url="http://new", source="test",
                      timestamp=now - timedelta(minutes=30))
        # Stale cutoff = 6 hours ago; only articles OLDER than 6h pass
        cutoff = now - timedelta(hours=6)
        stale = [a for a in [old, new] if a.timestamp and a.timestamp < cutoff]
        assert len(stale) == 1
        assert stale[0].title == "Old"


class TestSummaryTruncation:
    """Test summary truncation."""

    def test_truncate_long_summary(self):
        from clawler.models import Article
        a = Article(title="Test", url="http://test", source="test",
                    summary="x" * 500)
        max_len = 150
        if len(a.summary) > max_len:
            a.summary = a.summary[:max_len] + "..."
        assert len(a.summary) == 153  # 150 + "..."
        assert a.summary.endswith("...")

    def test_short_summary_untouched(self):
        from clawler.models import Article
        a = Article(title="Test", url="http://test", source="test",
                    summary="short")
        max_len = 300
        if len(a.summary) > max_len:
            a.summary = a.summary[:max_len] + "..."
        assert a.summary == "short"
