"""Tests for the shared parse_since utility."""
import pytest
from datetime import datetime, timezone, timedelta
from clawler.utils import parse_since


def test_minutes():
    before = datetime.now(timezone.utc)
    result = parse_since("30m")
    after = datetime.now(timezone.utc)
    assert before - timedelta(minutes=31) < result < after - timedelta(minutes=29)


def test_hours():
    result = parse_since("2h")
    expected = datetime.now(timezone.utc) - timedelta(hours=2)
    assert abs((result - expected).total_seconds()) < 2


def test_days():
    result = parse_since("1d")
    expected = datetime.now(timezone.utc) - timedelta(days=1)
    assert abs((result - expected).total_seconds()) < 2


def test_weeks():
    result = parse_since("1w")
    expected = datetime.now(timezone.utc) - timedelta(weeks=1)
    assert abs((result - expected).total_seconds()) < 2


def test_invalid_raises():
    with pytest.raises(ValueError):
        parse_since("abc")

    with pytest.raises(ValueError):
        parse_since("10x")
