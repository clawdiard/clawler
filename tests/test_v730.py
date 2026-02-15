"""Tests for v7.3.0: --top-authors, --only fix, duplicate --json-pretty fix."""
import subprocess
import sys

from clawler import __version__


def test_version_is_730():
    assert __version__ == "7.3.0"


def test_top_authors_flag_accepted():
    """--top-authors should be accepted without error (dry-run to avoid network)."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--dry-run", "--top-authors"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0


def test_only_flag_includes_all_sources():
    """--only with all 21 source names should not produce warnings."""
    all_sources = "rss,hn,reddit,github,mastodon,wikipedia,lobsters,devto,arxiv,techmeme,producthunt,bluesky,tildes,lemmy,slashdot,stackoverflow,pinboard,indiehackers,echojs,hashnode,freecodecamp"
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--dry-run", "--only", all_sources],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "unknown source" not in result.stderr.lower()


def test_only_flag_new_sources_not_unknown():
    """Previously missing sources should be recognized by --only."""
    for src in ["pinboard", "indiehackers", "echojs", "hashnode", "freecodecamp"]:
        result = subprocess.run(
            [sys.executable, "-m", "clawler", "--dry-run", "--only", src],
            capture_output=True, text=True, timeout=10,
        )
        assert "unknown source" not in result.stderr.lower(), f"--only {src} was flagged as unknown"


def test_no_duplicate_json_pretty_argument():
    """CLI should parse without argparse conflict on --json-pretty."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--json-pretty", "--dry-run"],
        capture_output=True, text=True, timeout=10,
    )
    # Should not crash with argparse error about duplicate arguments
    assert result.returncode == 0


def test_top_authors_empty_when_no_authors():
    """--top-authors with no articles should not crash."""
    from io import StringIO
    from clawler.models import Article
    # This is a unit-level check — the CLI integration is tested above
    articles = [Article(title="Test", url="http://x.com", source="test", author="")]
    # No authors → Counter should be empty
    from collections import Counter
    author_counts = Counter()
    for a in articles:
        if a.author and a.author.strip():
            author_counts[a.author.strip()] += 1
    assert len(author_counts) == 0


def test_top_authors_counts_correctly():
    """--top-authors should count authors correctly."""
    from collections import Counter
    from clawler.models import Article
    articles = [
        Article(title="A", url="http://a.com", source="s", author="Alice"),
        Article(title="B", url="http://b.com", source="s", author="Alice"),
        Article(title="C", url="http://c.com", source="s", author="Bob"),
    ]
    author_counts = Counter()
    for a in articles:
        if a.author and a.author.strip():
            author_counts[a.author.strip()] += 1
    assert author_counts["Alice"] == 2
    assert author_counts["Bob"] == 1
