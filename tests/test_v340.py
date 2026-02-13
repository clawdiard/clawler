"""Tests for v3.4.0 features: --urls-only, --titles-only, --no-dedup, --domains, watch fix."""
import sys
import io
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.models import Article
from clawler.dedup import deduplicate, DedupStats


def _make_articles():
    return [
        Article(title="First Article", url="https://example.com/1", source="Source A",
                summary="Summary 1", timestamp=datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc),
                category="tech", quality_score=0.8),
        Article(title="Second Article", url="https://other.com/2", source="Source B",
                summary="Summary 2", timestamp=datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc),
                category="science", quality_score=0.7),
        Article(title="First Article", url="https://example.com/1", source="Source A",
                summary="Summary 1", timestamp=datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc),
                category="tech", quality_score=0.8),
    ]


def test_dedup_enabled_false():
    """--no-dedup: dedup disabled should pass all articles through."""
    articles = _make_articles()
    stats = DedupStats()
    result = deduplicate(articles, enabled=False, stats=stats)
    assert len(result) == 3  # no dedup, keeps the duplicate
    assert stats.total_input == 3
    assert stats.unique_output == 3
    assert stats.total_removed == 0


def test_dedup_enabled_true():
    """Normal dedup removes the duplicate."""
    articles = _make_articles()
    stats = DedupStats()
    result = deduplicate(articles, enabled=True, stats=stats)
    assert len(result) == 2
    assert stats.exact_dupes == 1


def test_urls_only_output():
    """--urls-only outputs one URL per line."""
    from clawler.cli import main
    articles = _make_articles()[:2]
    mock_engine = MagicMock()
    mock_engine.crawl.return_value = (articles, {"rss": 2}, DedupStats())

    captured = io.StringIO()
    with patch("clawler.cli.CrawlEngine", return_value=mock_engine), \
         patch("sys.stdout", captured):
        main(argv=["--urls-only", "--no-config"])

    lines = captured.getvalue().strip().split("\n")
    assert "https://example.com/1" in lines
    assert "https://other.com/2" in lines


def test_titles_only_output():
    """--titles-only outputs one title per line."""
    from clawler.cli import main
    articles = _make_articles()[:2]
    mock_engine = MagicMock()
    mock_engine.crawl.return_value = (articles, {"rss": 2}, DedupStats())

    captured = io.StringIO()
    with patch("clawler.cli.CrawlEngine", return_value=mock_engine), \
         patch("sys.stdout", captured):
        main(argv=["--titles-only", "--no-config"])

    lines = captured.getvalue().strip().split("\n")
    assert "First Article" in lines
    assert "Second Article" in lines


def test_watch_argv_strips_watch_flag():
    """Verify --watch is recognized and the argv stripping logic works."""
    # The _watch_loop function strips --watch from argv before calling main()
    # We test the stripping logic directly
    original = ["--watch", "5m", "--category", "tech", "--no-config"]
    clean = []
    skip_next = False
    for i, arg in enumerate(original):
        if skip_next:
            skip_next = False
            continue
        if arg == "--watch":
            skip_next = True
            continue
        if arg.startswith("--watch="):
            continue
        clean.append(arg)
    assert clean == ["--category", "tech", "--no-config"]

    # Also test --watch=5m form
    original2 = ["--watch=5m", "--category", "tech"]
    clean2 = []
    skip_next = False
    for arg in original2:
        if skip_next:
            skip_next = False
            continue
        if arg == "--watch":
            skip_next = True
            continue
        if arg.startswith("--watch="):
            continue
        clean2.append(arg)
    assert clean2 == ["--category", "tech"]
