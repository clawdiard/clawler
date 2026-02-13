"""Tests for clawler.utils.parse_since_seconds."""
from clawler.utils import parse_since_seconds
import pytest


def test_seconds():
    assert parse_since_seconds("30s") == 30


def test_minutes():
    assert parse_since_seconds("5m") == 300


def test_hours():
    assert parse_since_seconds("12h") == 43200


def test_days():
    assert parse_since_seconds("2d") == 172800


def test_weeks():
    assert parse_since_seconds("1w") == 604800


def test_months():
    assert parse_since_seconds("3M") == 7776000


def test_years():
    assert parse_since_seconds("1y") == 31536000


def test_invalid():
    with pytest.raises(ValueError):
        parse_since_seconds("abc")
