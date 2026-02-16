"""Tests for v8.5.0 — --only completeness and --dry-run coverage."""
import subprocess
import sys


def test_only_recognizes_all_registry_sources():
    """--only should accept all sources in _SOURCE_REGISTRY without warnings."""
    all_sources = (
        "rss,hn,reddit,github,mastodon,wikipedia,lobsters,devto,arxiv,"
        "techmeme,producthunt,bluesky,tildes,lemmy,slashdot,stackoverflow,"
        "pinboard,indiehackers,echojs,hashnode,freecodecamp,youtube,medium,"
        "substack,googlenews,dzone,sciencedaily,npr,changelog,hackernoon"
    )
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--only", all_sources, "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Warning: unknown source" not in result.stderr
    assert "Warning: unknown source" not in result.stdout


def test_only_warns_on_unknown():
    """--only should warn about genuinely unknown sources."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--only", "rss,fakesource", "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "fakesource" in result.stderr or "fakesource" in result.stdout


def test_dry_run_lists_all_sources():
    """--dry-run should mention all 30+ sources."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    output = result.stdout
    for label in ["RSS", "Hacker News", "Reddit", "GitHub", "Mastodon",
                   "Wikipedia", "Lobsters", "Dev.to", "ArXiv", "TechMeme",
                   "ProductHunt", "Bluesky", "YouTube", "Medium", "Substack",
                   "Google News", "DZone", "ScienceDaily", "NPR",
                   "Tildes", "Lemmy", "Slashdot", "Stack Overflow", "Pinboard",
                   "Indie Hackers", "EchoJS", "Hashnode", "freeCodeCamp",
                   "Changelog", "Hacker Noon"]:
        assert label in output, f"--dry-run missing: {label}"


def test_version_bump():
    """Version should be 8.5.0."""
    from clawler import __version__
    assert __version__ == "8.5.0"
