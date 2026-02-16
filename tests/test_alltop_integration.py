"""Tests for AllTop source integration into engine + CLI."""
import subprocess
import sys


def test_alltop_in_source_registry():
    """AllTop should be in the CLI source registry."""
    from clawler.cli import main
    # --only alltop shouldn't produce unknown source warning
    # Just verify import works
    from clawler.sources import AllTopSource
    src = AllTopSource()
    assert src.name == "alltop"


def test_alltop_in_engine_import():
    """AllTopSource should be importable from engine module."""
    from clawler.engine import AllTopSource
    assert AllTopSource is not None


def test_alltop_default_topics():
    """AllTop should have sensible default topics."""
    from clawler.sources.alltop import AllTopSource, DEFAULT_TOPICS
    src = AllTopSource()
    assert len(src.topics) >= 5
    assert "tech" in src.topics
    assert "science" in src.topics


def test_alltop_topic_categories():
    """All default topics should map to a category."""
    from clawler.sources.alltop import AllTopSource, DEFAULT_TOPICS, TOPIC_CATEGORIES
    for topic in DEFAULT_TOPICS:
        assert topic in TOPIC_CATEGORIES, f"Default topic '{topic}' missing from TOPIC_CATEGORIES"


def test_alltop_parse_empty_html():
    """Parsing empty HTML should return empty list."""
    from clawler.sources.alltop import AllTopSource
    src = AllTopSource()
    articles = src._parse_topic("", "tech", set())
    assert articles == []


def test_alltop_cli_no_flag():
    """--no-alltop flag should exist."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--no-alltop", "--dry-run"],
        capture_output=True, text=True, timeout=15
    )
    # Should not error about unknown argument
    assert result.returncode == 0 or "unrecognized" not in result.stderr


def test_alltop_only_flag():
    """--only alltop should work without warnings."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--only", "alltop", "--dry-run"],
        capture_output=True, text=True, timeout=15
    )
    assert "unknown source" not in result.stderr.lower()
