"""Tests for v10.40.0: fix registry counts, export-sources, retry tracking."""
import json
import os
import tempfile
import pytest
from clawler import __version__
from clawler.health import HealthTracker
from clawler.registry import SOURCES


def test_version_bump():
    assert __version__ == "10.40.0"


def test_registry_count_is_64():
    """Ensure registry count matches the 64 registered sources."""
    assert len(SOURCES) == 64


def test_health_retry_tracking():
    """HealthTracker.record_success should track retries_used."""
    tracker = HealthTracker()
    tracker.data = {}  # start fresh
    tracker.record_success("test_source", 10, response_ms=500, retries_used=2)
    assert tracker.data["test_source"]["retries_used"] == 2
    tracker.record_success("test_source", 5, response_ms=300, retries_used=1)
    assert tracker.data["test_source"]["retries_used"] == 3
    # Zero retries should not add the key
    tracker.record_success("clean_source", 8, response_ms=200, retries_used=0)
    assert "retries_used" not in tracker.data["clean_source"]


def test_export_sources_cli():
    """--export-sources should write a valid JSON file."""
    from clawler.cli import main
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        main(["--export-sources", path])
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 64
        assert all("key" in entry and "name" in entry for entry in data)
        assert data[0]["key"] == "rss"
    finally:
        os.unlink(path)
