"""Tests for health tracker percentile stats."""
from clawler.health import HealthTracker


def test_percentile_basic():
    ht = HealthTracker()
    vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert ht._percentile(vals, 50) == 55.0
    assert ht._percentile(vals, 0) == 10
    assert ht._percentile(vals, 100) == 100


def test_percentile_single():
    ht = HealthTracker()
    assert ht._percentile([42], 50) == 42
    assert ht._percentile([42], 99) == 42


def test_percentile_empty():
    ht = HealthTracker()
    assert ht._percentile([], 50) == 0.0


def test_timing_report_has_percentiles():
    ht = HealthTracker()
    ht.data = {
        "test_source": {
            "total_crawls": 10,
            "failures": 0,
            "total_articles": 50,
            "last_success": None,
            "response_times_ms": [100, 200, 300, 400, 500, 150, 250, 350, 450, 550],
        }
    }
    report = ht.get_timing_report()
    assert len(report) == 1
    entry = report[0]
    assert "p50_ms" in entry
    assert "p95_ms" in entry
    assert "p99_ms" in entry
    assert entry["min_ms"] == 100
    assert entry["max_ms"] == 550
    assert entry["samples"] == 10
