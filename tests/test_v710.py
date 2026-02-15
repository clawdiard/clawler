"""Tests for v7.1.0: reading time estimation, --min-read/--max-read filters, --show-read-time."""
import subprocess
import sys
from clawler.models import Article
from clawler.readtime import estimate_read_minutes, format_read_time, filter_by_read_time


def _make_article(title="Test", summary="", **kw):
    return Article(title=title, url="https://example.com", source="test", summary=summary, **kw)


def test_estimate_short_summary():
    a = _make_article(summary="Short article about AI.")
    rt = estimate_read_minutes(a)
    assert rt == 2, f"Expected 2 min for short summary, got {rt}"


def test_estimate_medium_summary():
    words = " ".join(["word"] * 80)
    a = _make_article(summary=words)
    rt = estimate_read_minutes(a)
    assert 3 <= rt <= 5, f"Expected 3-5 min for medium summary, got {rt}"


def test_estimate_long_summary():
    words = " ".join(["word"] * 200)
    a = _make_article(summary=words)
    rt = estimate_read_minutes(a)
    assert rt >= 5, f"Expected >= 5 min for long summary, got {rt}"


def test_estimate_empty_summary():
    a = _make_article(summary="")
    rt = estimate_read_minutes(a)
    assert rt >= 1, "Reading time should be at least 1 minute"


def test_format_read_time():
    assert format_read_time(1) == "1 min read"
    assert format_read_time(5) == "5 min read"
    assert format_read_time(0) == "<1 min"


def test_filter_min_read():
    articles = [
        _make_article(title="Short", summary="brief"),
        _make_article(title="Long", summary=" ".join(["word"] * 200)),
    ]
    filtered = filter_by_read_time(articles, min_minutes=4)
    assert len(filtered) == 1
    assert filtered[0].title == "Long"


def test_filter_max_read():
    articles = [
        _make_article(title="Short", summary="brief"),
        _make_article(title="Long", summary=" ".join(["word"] * 200)),
    ]
    filtered = filter_by_read_time(articles, max_minutes=3)
    assert len(filtered) == 1
    assert filtered[0].title == "Short"


def test_filter_both():
    articles = [
        _make_article(title="Short", summary="brief"),
        _make_article(title="Medium", summary=" ".join(["word"] * 80)),
        _make_article(title="Long", summary=" ".join(["word"] * 200)),
    ]
    filtered = filter_by_read_time(articles, min_minutes=2, max_minutes=4)
    titles = [a.title for a in filtered]
    assert "Short" in titles
    assert "Long" not in titles


def test_filter_none_passthrough():
    articles = [_make_article(summary="anything")]
    assert filter_by_read_time(articles) == articles


def test_cli_min_read_flag():
    """--min-read is accepted without error."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--min-read", "3", "--limit", "0"],
        capture_output=True, text=True, timeout=30,
    )
    # Should not crash (exit 0 or normal output)
    assert result.returncode == 0 or "error" not in result.stderr.lower()


def test_cli_max_read_flag():
    """--max-read is accepted without error."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--max-read", "5", "--limit", "0"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0 or "error" not in result.stderr.lower()


def test_cli_show_read_time_flag():
    """--show-read-time is accepted without error."""
    result = subprocess.run(
        [sys.executable, "-m", "clawler", "--show-read-time", "--limit", "0"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0 or "error" not in result.stderr.lower()


def test_version_is_710():
    from clawler import __version__
    assert __version__ == "7.1.0", f"Expected 7.1.0, got {__version__}"
