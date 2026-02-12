"""Tests for CLI utilities."""
import argparse
import pytest
from datetime import datetime, timezone, timedelta
from clawler.cli import _parse_since


class TestParseSince:
    def test_hours(self):
        result = _parse_since("2h")
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        # Should be roughly 2 hours ago
        diff = datetime.now(timezone.utc) - result
        assert timedelta(hours=1, minutes=59) < diff < timedelta(hours=2, minutes=1)

    def test_minutes(self):
        result = _parse_since("30m")
        diff = datetime.now(timezone.utc) - result
        assert timedelta(minutes=29) < diff < timedelta(minutes=31)

    def test_days(self):
        result = _parse_since("1d")
        diff = datetime.now(timezone.utc) - result
        assert timedelta(hours=23) < diff < timedelta(hours=25)

    def test_weeks(self):
        result = _parse_since("1w")
        diff = datetime.now(timezone.utc) - result
        assert timedelta(days=6) < diff < timedelta(days=8)

    def test_invalid_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_since("abc")

    def test_invalid_unit_raises(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_since("5x")
