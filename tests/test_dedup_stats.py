"""Tests for DedupStats."""
from clawler.dedup import deduplicate, DedupStats
from clawler.models import Article


def _art(title, url="https://example.com", source="Test", quality=0.5):
    return Article(title=title, url=url, source=source, quality_score=quality)


def test_dedup_stats_exact():
    stats = DedupStats()
    articles = [
        _art("Hello World", url="https://a.com"),
        _art("Hello World", url="https://a.com"),  # exact dupe
    ]
    result = deduplicate(articles, stats=stats)
    assert len(result) == 1
    assert stats.exact_dupes == 1
    assert stats.total_removed == 1


def test_dedup_stats_fuzzy():
    stats = DedupStats()
    articles = [
        _art("Breaking: Major Event Happens Today", url="https://a.com", source="A", quality=0.8),
        _art("Breaking: Major Event Happens Today!", url="https://b.com", source="B", quality=0.5),
    ]
    result = deduplicate(articles, stats=stats)
    assert len(result) == 1
    assert stats.total_removed >= 1


def test_dedup_stats_summary():
    stats = DedupStats()
    stats.total_input = 10
    stats.exact_dupes = 2
    stats.fingerprint_dupes = 1
    stats.fuzzy_dupes = 1
    stats.unique_output = 6
    summary = stats.summary()
    assert "10 → 6" in summary
    assert "removed 4" in summary


def test_dedup_stats_no_dupes():
    stats = DedupStats()
    articles = [
        _art("Alpha", url="https://a.com"),
        _art("Beta", url="https://b.com"),
    ]
    result = deduplicate(articles, stats=stats)
    assert len(result) == 2
    assert stats.total_removed == 0
    assert stats.unique_output == 2
