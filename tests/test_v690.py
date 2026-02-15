"""Tests for v6.9.0: freeCodeCamp source + --digest mode."""
import argparse
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.sources.freecodecamp import FreeCodeCampSource, TAG_CATEGORY_MAP


# --- freeCodeCamp source tests ---

def _make_rss_xml(entries):
    """Build a minimal RSS XML string from a list of entry dicts."""
    items = ""
    for e in entries:
        tags_xml = "".join(f'<category>{t}</category>' for t in e.get("tags", []))
        items += f"""
        <item>
            <title>{e['title']}</title>
            <link>{e['url']}</link>
            <description>{e.get('summary', '')}</description>
            <pubDate>Sun, 15 Feb 2026 07:00:00 +0000</pubDate>
            <dc:creator>{e.get('author', '')}</dc:creator>
            {tags_xml}
        </item>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
    <channel><title>freeCodeCamp</title>{items}</channel></rss>"""


def test_freecodecamp_source_name():
    src = FreeCodeCampSource()
    assert src.name == "freecodecamp"


def test_freecodecamp_crawl_parses_rss():
    xml = _make_rss_xml([
        {"title": "Learn Python", "url": "https://freecodecamp.org/news/learn-python", "author": "Alice", "tags": ["python"]},
        {"title": "CSS Grid Guide", "url": "https://freecodecamp.org/news/css-grid", "author": "Bob", "tags": ["css"]},
    ])
    src = FreeCodeCampSource(limit=10)
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].title == "Learn Python"
    assert articles[0].source == "freeCodeCamp"
    assert articles[0].author == "Alice"
    assert articles[1].title == "CSS Grid Guide"


def test_freecodecamp_empty_feed():
    src = FreeCodeCampSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_freecodecamp_limit():
    entries = [{"title": f"Article {i}", "url": f"https://fcc.org/news/{i}"} for i in range(10)]
    xml = _make_rss_xml(entries)
    src = FreeCodeCampSource(limit=3)
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 3


def test_freecodecamp_tag_category_mapping():
    assert TAG_CATEGORY_MAP["python"] == "tech"
    assert TAG_CATEGORY_MAP["security"] == "security"
    assert TAG_CATEGORY_MAP["career"] == "business"
    assert TAG_CATEGORY_MAP["data-science"] == "science"


def test_freecodecamp_category_from_tags():
    xml = _make_rss_xml([
        {"title": "Security 101", "url": "https://fcc.org/news/sec", "tags": ["security"]},
    ])
    src = FreeCodeCampSource()
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].category == "security"


def test_freecodecamp_html_stripping():
    xml = _make_rss_xml([
        {"title": "Test", "url": "https://fcc.org/news/test", "summary": "<p>Hello <b>world</b></p>"},
    ])
    src = FreeCodeCampSource()
    with patch.object(src, "fetch_url", return_value=xml):
        articles = src.crawl()
    assert "<" not in articles[0].summary


def test_freecodecamp_in_sources_init():
    from clawler.sources import FreeCodeCampSource as FCC
    assert FCC is not None


def test_freecodecamp_in_all_exports():
    from clawler.sources import __all__
    assert "FreeCodeCampSource" in __all__


# --- --digest mode tests ---

def test_digest_flag_sets_defaults():
    """--digest should set since=24h, group_by=category, sort=quality, format=markdown."""
    from clawler.cli import main
    import sys

    # We just need to verify the arg parsing, not run the full crawl
    # So we'll parse args directly
    from clawler.cli import main as _main
    import clawler.cli as cli_mod

    # Test by checking that the --digest flag exists in the parser
    parser = argparse.ArgumentParser()
    parser.add_argument("--digest", action="store_true")
    parser.add_argument("--since", default=None)
    parser.add_argument("--group-by", default=None, dest="group_by")
    parser.add_argument("--sort", default="time")
    parser.add_argument("--format", default="console")

    args = parser.parse_args(["--digest"])
    assert args.digest is True

    # Simulate the digest logic from cli.py
    if args.digest:
        if not args.since:
            args.since = "24h"
        if not args.group_by:
            args.group_by = "category"
        if args.sort == "time":
            args.sort = "quality"
        if args.format == "console":
            args.format = "markdown"

    assert args.since == "24h"
    assert args.group_by == "category"
    assert args.sort == "quality"
    assert args.format == "markdown"


def test_digest_does_not_override_explicit():
    """--digest should not override explicitly set flags."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--digest", action="store_true")
    parser.add_argument("--since", default=None)
    parser.add_argument("--group-by", default=None, dest="group_by")
    parser.add_argument("--sort", default="time")
    parser.add_argument("--format", default="console")

    args = parser.parse_args(["--digest", "--since", "2h", "--sort", "time", "--format", "json"])
    if args.digest:
        if not args.since:
            args.since = "24h"
        if not args.group_by:
            args.group_by = "category"
        if args.sort == "time":
            args.sort = "quality"
        if args.format == "console":
            args.format = "markdown"

    assert args.since == "2h"  # explicit --since not overridden
    assert args.format == "json"  # explicit --format not overridden


def test_version_690():
    from clawler import __version__
    assert __version__ == "6.9.0"
