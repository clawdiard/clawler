"""Tests for the cache module."""
import time
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from clawler.cache import cache_key, save_cache, load_cache, clear_cache
from clawler.models import Article


def _make_articles():
    return [
        Article(
            title="Test Article",
            url="https://example.com/1",
            source="Test",
            summary="A test article",
            timestamp=datetime(2026, 2, 12, 12, 0, 0, tzinfo=timezone.utc),
            category="tech",
        ),
        Article(
            title="Another Article",
            url="https://example.com/2",
            source="Test",
            summary="Another test",
            timestamp=None,
            category="world",
        ),
    ]


class TestCacheKey:
    def test_deterministic(self):
        k1 = cache_key(["rss", "hackernews"], 0.75)
        k2 = cache_key(["rss", "hackernews"], 0.75)
        assert k1 == k2

    def test_order_independent(self):
        k1 = cache_key(["rss", "hackernews"], 0.75)
        k2 = cache_key(["hackernews", "rss"], 0.75)
        assert k1 == k2

    def test_different_threshold(self):
        k1 = cache_key(["rss"], 0.75)
        k2 = cache_key(["rss"], 0.85)
        assert k1 != k2


class TestSaveLoad:
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            articles = _make_articles()
            stats = {"rss": 10, "hackernews": 5}
            save_cache("test", articles, stats, cache_dir=d)
            result = load_cache("test", ttl=60, cache_dir=d)
            assert result is not None
            loaded_articles, loaded_stats = result
            assert len(loaded_articles) == 2
            assert loaded_articles[0].title == "Test Article"
            assert loaded_articles[1].timestamp is None
            assert loaded_stats == stats

    def test_stale_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            save_cache("test", _make_articles(), {}, cache_dir=d)
            result = load_cache("test", ttl=0, cache_dir=d)
            assert result is None

    def test_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            result = load_cache("nonexistent", cache_dir=Path(td))
            assert result is None


class TestClearCache:
    def test_clears(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            save_cache("a", _make_articles(), {}, cache_dir=d)
            save_cache("b", _make_articles(), {}, cache_dir=d)
            n = clear_cache(cache_dir=d)
            assert n == 2
            assert load_cache("a", cache_dir=d) is None

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            assert clear_cache(cache_dir=Path(td)) == 0
