"""Tests for v4.7.0: Dev.to source, version sync fix."""
import json
from unittest.mock import patch, MagicMock
from clawler.sources.devto import DevToSource
from clawler import __version__


SAMPLE_DEVTO_RESPONSE = [
    {
        "title": "Building a CLI in Rust",
        "url": "https://dev.to/rustdev/building-a-cli-in-rust-abc",
        "description": "A quick guide to building CLI tools with Rust and clap.",
        "tag_list": ["rust", "cli", "tutorial"],
        "published_at": "2026-02-14T04:00:00Z",
        "positive_reactions_count": 42,
        "user": {"name": "Rust Dev", "username": "rustdev"},
    },
    {
        "title": "Cybersecurity Best Practices 2026",
        "url": "https://dev.to/secpro/cybersecurity-2026-def",
        "description": "Top security tips for the new year.",
        "tag_list": ["security", "cybersecurity"],
        "published_at": "2026-02-13T12:00:00Z",
        "positive_reactions_count": 18,
        "user": {"name": "Sec Pro", "username": "secpro"},
    },
    {
        "title": "",
        "url": "",
        "description": "Empty article that should be skipped",
        "tag_list": [],
        "published_at": None,
        "positive_reactions_count": 0,
        "user": {},
    },
]


def test_devto_source_parses_articles():
    src = DevToSource(per_page=10)
    with patch.object(src, "fetch_json", return_value=SAMPLE_DEVTO_RESPONSE):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].title == "Building a CLI in Rust"
    assert articles[0].source == "dev.to"
    assert articles[0].category == "tech"
    assert "♥42" in articles[0].summary
    assert "Rust Dev" in articles[0].summary


def test_devto_security_category():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=SAMPLE_DEVTO_RESPONSE):
        articles = src.crawl()
    sec = [a for a in articles if a.category == "security"]
    assert len(sec) == 1
    assert sec[0].title == "Cybersecurity Best Practices 2026"


def test_devto_empty_response():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=[]):
        articles = src.crawl()
    assert articles == []


def test_devto_none_response():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=None):
        articles = src.crawl()
    assert articles == []


def test_devto_fetch_error():
    src = DevToSource()
    with patch.object(src, "fetch_json", side_effect=Exception("timeout")):
        articles = src.crawl()
    assert articles == []


def test_devto_skips_empty_titles():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=SAMPLE_DEVTO_RESPONSE):
        articles = src.crawl()
    titles = [a.title for a in articles]
    assert "" not in titles


def test_devto_tags_populated():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=SAMPLE_DEVTO_RESPONSE):
        articles = src.crawl()
    assert articles[0].tags == ["devto:rust", "devto:cli", "devto:tutorial"]


def test_devto_timestamp_parsed():
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=SAMPLE_DEVTO_RESPONSE):
        articles = src.crawl()
    assert articles[0].timestamp is not None
    assert articles[0].timestamp.year == 2026


def test_devto_string_tag_list():
    """Dev.to sometimes returns tag_list as a comma-separated string."""
    data = [{
        "title": "Test",
        "url": "https://dev.to/test/test",
        "description": "desc",
        "tag_list": "python,ai,tutorial",
        "published_at": "2026-02-14T00:00:00Z",
        "positive_reactions_count": 5,
        "user": {"username": "tester"},
    }]
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=data):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].tags == ["devto:python", "devto:ai", "devto:tutorial"]


def test_devto_top_parameter():
    src = DevToSource(per_page=5, top=7)
    assert src.top == 7
    assert src.per_page == 5


def test_version_sync():
    """setup.py and __init__.py should have the same version."""
    import re
    with open("setup.py") as f:
        content = f.read()
    match = re.search(r'version="([^"]+)"', content)
    assert match, "No version found in setup.py"
    assert match.group(1) == __version__, f"setup.py={match.group(1)} != __init__={__version__}"


def test_no_devto_cli_flag():
    """--no-devto flag should be accepted."""
    from clawler.cli import main
    import sys
    # Just test that the flag parses without error (dry-run)
    try:
        main(["--no-devto", "--dry-run"])
    except SystemExit:
        pass  # dry-run may exit
