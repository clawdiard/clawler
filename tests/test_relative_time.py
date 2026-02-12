"""Tests for relative time and multi-category features."""
from datetime import datetime, timedelta, timezone
from clawler.utils import relative_time


class TestRelativeTime:
    def test_seconds_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(seconds=30)
        assert "30s ago" == relative_time(dt)

    def test_minutes_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert "5m ago" == relative_time(dt)

    def test_hours_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(hours=3)
        assert "3h ago" == relative_time(dt)

    def test_days_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(days=2)
        assert "2d ago" == relative_time(dt)

    def test_weeks_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(weeks=2)
        assert "2w ago" == relative_time(dt)

    def test_naive_datetime_treated_as_utc(self):
        dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        result = relative_time(dt)
        assert "1h ago" == result

    def test_just_now(self):
        dt = datetime.now(timezone.utc) + timedelta(seconds=5)
        assert "just now" == relative_time(dt)
