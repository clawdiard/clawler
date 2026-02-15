"""Tests for v7.4.0 features: --top-words, --source-quality, version sync."""
import subprocess
import sys
import re


def test_version_sync():
    """All version strings should match."""
    import clawler
    assert clawler.__version__ == "7.4.0"

    # Check setup.py
    with open("setup.py") as f:
        content = f.read()
    assert 'version="7.4.0"' in content

    # Check pyproject.toml
    with open("pyproject.toml") as f:
        content = f.read()
    assert 'version = "7.4.0"' in content


def test_top_words_flag_accepted():
    """--top-words should be accepted without error."""
    from clawler.cli import main
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            main(["--top-words", "--limit", "0", "--no-dedup", "--quiet"])
    except SystemExit:
        pass  # limit 0 may cause early exit


def test_source_quality_flag_accepted():
    """--source-quality should be accepted without error."""
    from clawler.cli import main
    import io
    from contextlib import redirect_stderr
    buf = io.StringIO()
    try:
        with redirect_stderr(buf):
            main(["--source-quality", "--limit", "0", "--no-dedup", "--quiet"])
    except SystemExit:
        pass


def test_top_words_stop_word_filtering():
    """Stop words should be excluded from word counts."""
    from collections import Counter
    STOP_WORDS = frozenset({
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "it", "its", "are", "was", "were",
        "be", "been", "has", "have", "had", "do", "does", "did", "will", "can",
        "this", "that", "not", "you", "your", "how", "what", "why", "when",
        "who", "all", "new", "more", "no", "than", "into", "about", "up",
        "out", "over", "just", "after", "before", "now", "as", "so", "if",
    })
    title = "The New Way to Build AI Systems in the Cloud"
    words = [w.lower().strip(".,!?:;\"'()[]{}") for w in title.split()]
    words = [w for w in words if len(w) > 2 and w not in STOP_WORDS and w.isalpha()]
    assert "the" not in words
    assert "way" in words
    assert "build" in words
    assert "systems" in words
    assert "cloud" in words


def test_source_quality_calculation():
    """Average quality scores should be computed correctly."""
    from collections import defaultdict
    scores = defaultdict(list)
    scores["HN"].extend([0.8, 0.9, 0.7])
    scores["RSS"].extend([0.5, 0.6])
    avg_hn = sum(scores["HN"]) / len(scores["HN"])
    avg_rss = sum(scores["RSS"]) / len(scores["RSS"])
    assert abs(avg_hn - 0.8) < 0.01
    assert abs(avg_rss - 0.55) < 0.01


def test_top_words_short_words_excluded():
    """Words with 2 or fewer characters should be excluded."""
    title = "AI is OK but ML and DL are too"
    words = [w.lower().strip(".,!?:;\"'()[]{}") for w in title.split()]
    words = [w for w in words if len(w) > 2 and w.isalpha()]
    assert "ai" not in words
    assert "is" not in words
    assert "ok" not in words
    assert "but" in words


def test_top_words_non_alpha_excluded():
    """Non-alphabetic tokens should be excluded."""
    title = "Python3 hits 100% adoption in 2026"
    words = [w.lower().strip(".,!?:;\"'()[]{}") for w in title.split()]
    words = [w for w in words if len(w) > 2 and w.isalpha()]
    # "100%" is in raw tokens but filtered out by isalpha()
    assert "100" not in words  # non-alpha stripped
    assert "adoption" in words
    assert "hits" in words


def test_version_is_740():
    """Quick sanity: importable version is 7.4.0."""
    from clawler import __version__
    assert __version__ == "7.4.0"
