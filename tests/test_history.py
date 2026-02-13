"""Tests for clawler.history — persistent dedup history."""
import json
import time
from pathlib import Path
from clawler.history import filter_seen, clear_history, history_stats, _history_path
from clawler.models import Article


def _make_article(title="Test Article", url="https://example.com/1", source="Test"):
    return Article(title=title, url=url, source=source)


def test_filter_seen_first_run(tmp_path):
    """First run: all articles are new."""
    articles = [_make_article(f"Article {i}", f"https://ex.com/{i}") for i in range(5)]
    result = filter_seen(articles, ttl=3600, history_dir=tmp_path)
    assert len(result) == 5


def test_filter_seen_second_run_deduplicates(tmp_path):
    """Second run with same articles: all filtered out."""
    articles = [_make_article(f"Article {i}", f"https://ex.com/{i}") for i in range(5)]
    filter_seen(articles, ttl=3600, history_dir=tmp_path)
    result = filter_seen(articles, ttl=3600, history_dir=tmp_path)
    assert len(result) == 0


def test_filter_seen_new_articles_pass(tmp_path):
    """New articles pass through even after previous run."""
    old = [_make_article(f"Old {i}", f"https://ex.com/old/{i}") for i in range(3)]
    filter_seen(old, ttl=3600, history_dir=tmp_path)
    new = [_make_article(f"New {i}", f"https://ex.com/new/{i}") for i in range(2)]
    result = filter_seen(new, ttl=3600, history_dir=tmp_path)
    assert len(result) == 2


def test_filter_seen_mixed(tmp_path):
    """Mix of old and new articles."""
    batch1 = [_make_article("Seen", "https://ex.com/seen")]
    filter_seen(batch1, ttl=3600, history_dir=tmp_path)
    batch2 = [
        _make_article("Seen", "https://ex.com/seen"),
        _make_article("Fresh", "https://ex.com/fresh"),
    ]
    result = filter_seen(batch2, ttl=3600, history_dir=tmp_path)
    assert len(result) == 1
    assert result[0].title == "Fresh"


def test_expired_entries_pruned(tmp_path):
    """Articles older than TTL should be forgotten."""
    articles = [_make_article("Expire Me", "https://ex.com/expire")]
    filter_seen(articles, ttl=1, history_dir=tmp_path)
    # Manually age the entry
    path = _history_path(tmp_path)
    data = json.loads(path.read_text())
    for fp in data["seen"]:
        data["seen"][fp] = time.time() - 10
    path.write_text(json.dumps(data))
    # Should pass through now
    result = filter_seen(articles, ttl=1, history_dir=tmp_path)
    assert len(result) == 1


def test_clear_history(tmp_path):
    """clear_history removes the file."""
    articles = [_make_article()]
    filter_seen(articles, ttl=3600, history_dir=tmp_path)
    assert _history_path(tmp_path).exists()
    assert clear_history(tmp_path) is True
    assert not _history_path(tmp_path).exists()
    assert clear_history(tmp_path) is False


def test_history_stats_empty(tmp_path):
    """Stats on empty history."""
    stats = history_stats(ttl=3600, history_dir=tmp_path)
    assert stats["total_entries"] == 0
    assert stats["active_entries"] == 0


def test_history_stats_populated(tmp_path):
    """Stats after recording articles."""
    articles = [_make_article(f"Art {i}", f"https://ex.com/{i}") for i in range(3)]
    filter_seen(articles, ttl=3600, history_dir=tmp_path)
    stats = history_stats(ttl=3600, history_dir=tmp_path)
    assert stats["active_entries"] > 0
    assert stats["oldest_age_hours"] is not None
