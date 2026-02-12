"""Tests for models and deduplication."""
from datetime import datetime, timezone
from clawler.models import Article
from clawler.dedup import deduplicate


def _article(title="Test", url="https://example.com", source="test", **kw):
    return Article(title=title, url=url, source=source, **kw)


class TestArticle:
    def test_dedup_key_deterministic(self):
        a = _article(title="Hello World", url="https://example.com/1")
        b = _article(title="Hello World", url="https://example.com/1")
        assert a.dedup_key == b.dedup_key

    def test_dedup_key_case_insensitive(self):
        a = _article(title="Hello World")
        b = _article(title="hello world")
        assert a.dedup_key == b.dedup_key

    def test_different_urls_different_keys(self):
        a = _article(url="https://a.com")
        b = _article(url="https://b.com")
        assert a.dedup_key != b.dedup_key


class TestDedup:
    def test_exact_dedup(self):
        articles = [
            _article(title="Same", url="https://a.com/1"),
            _article(title="Same", url="https://a.com/1"),
        ]
        assert len(deduplicate(articles)) == 1

    def test_fuzzy_dedup(self):
        articles = [
            _article(title="Breaking: Major earthquake hits California coast", url="https://a.com"),
            _article(title="Breaking: Major earthquake hits California coast today", url="https://b.com"),
        ]
        result = deduplicate(articles, similarity_threshold=0.75)
        assert len(result) == 1

    def test_different_stories_kept(self):
        articles = [
            _article(title="Python 4.0 released", url="https://a.com"),
            _article(title="NASA discovers new exoplanet", url="https://b.com"),
        ]
        assert len(deduplicate(articles)) == 2

    def test_empty_input(self):
        assert deduplicate([]) == []
