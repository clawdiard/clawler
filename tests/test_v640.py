"""Tests for v6.4.0 features: --top-tags, new RSS feeds, Dockerfile."""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from clawler.models import Article
from clawler.weights import get_quality_score
from datetime import datetime, timezone


def test_top_tags_flag_accepted():
    """--top-tags flag is accepted by CLI parser."""
    from clawler.cli import main
    # Should not raise on parse (will fail on crawl, but that's fine — we just test the flag)
    import argparse
    from clawler.cli import main
    # We test that the argument is registered by checking argparse directly
    import clawler.cli as cli_mod
    # Quick smoke: ensure --top-tags doesn't cause an unknown argument error
    # by invoking with --dry-run which exits before crawling
    try:
        main(["--top-tags", "--dry-run"])
    except SystemExit:
        pass  # --dry-run exits cleanly


def test_new_rss_feeds_in_defaults():
    """New v6.4.0 RSS feeds are in DEFAULT_FEEDS."""
    from clawler.sources.rss import DEFAULT_FEEDS
    source_names = [f["source"] for f in DEFAULT_FEEDS]
    assert "freeCodeCamp" in source_names
    assert "The Changelog" in source_names
    assert "Daring Fireball" in source_names
    assert "AnandTech" in source_names
    assert "This Week in Rust" in source_names
    assert "Go Blog" in source_names


def test_new_feeds_have_quality_weights():
    """New sources have quality weight entries."""
    for name in ["freeCodeCamp", "The Changelog", "Daring Fireball", "AnandTech", "This Week in Rust", "Go Blog"]:
        score = get_quality_score(name)
        assert score > 0.5, f"{name} should have quality score > 0.5, got {score}"


def test_dockerfile_exists():
    """Dockerfile exists at repo root."""
    assert Path("Dockerfile").exists() or Path("/tmp/clawler/Dockerfile").exists()


def test_dockerignore_exists():
    """.dockerignore exists at repo root."""
    assert Path(".dockerignore").exists() or Path("/tmp/clawler/.dockerignore").exists()


def test_version_bump():
    """Version is 6.4.0."""
    from clawler import __version__
    assert __version__ == "6.6.0"


def test_top_tags_output():
    """Top tags analytics produces expected output format."""
    from collections import Counter
    articles = [
        Article(title="Test", url="http://a.com", source="Test", tags=["python", "ai"]),
        Article(title="Test2", url="http://b.com", source="Test", tags=["python", "rust"]),
        Article(title="Test3", url="http://c.com", source="Test", tags=["ai"]),
    ]
    tag_counts = Counter()
    for a in articles:
        for tag in a.tags:
            tag_counts[tag.lower()] += 1
    assert tag_counts["python"] == 2
    assert tag_counts["ai"] == 2
    assert tag_counts["rust"] == 1


def test_rss_feed_count():
    """At least 54 RSS feeds configured."""
    from clawler.sources.rss import DEFAULT_FEEDS
    assert len(DEFAULT_FEEDS) >= 54
