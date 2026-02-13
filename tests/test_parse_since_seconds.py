"""Tests for seconds unit support in parse_since (v2.9.0)."""
from datetime import datetime, timezone, timedelta
from clawler.utils import parse_since


def test_seconds():
    result = parse_since("30s")
    expected = datetime.now(timezone.utc) - timedelta(seconds=30)
    assert abs((result - expected).total_seconds()) < 2


def test_seconds_single():
    result = parse_since("1s")
    expected = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert abs((result - expected).total_seconds()) < 2
