"""Tests for enhanced URL normalization (tracking param stripping)."""
import pytest
from clawler.models import _normalize_url, Article


class TestNormalizeUrl:
    def test_strips_www(self):
        assert _normalize_url("https://www.example.com/article") == "https://example.com/article"

    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/article/") == "https://example.com/article"

    def test_strips_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social&id=123"
        result = _normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=123" in result

    def test_strips_fbclid(self):
        url = "https://example.com/post?fbclid=abc123"
        assert _normalize_url(url) == "https://example.com/post"

    def test_strips_gclid(self):
        url = "https://example.com/page?gclid=xyz&page=2"
        result = _normalize_url(url)
        assert "gclid" not in result
        assert "page=2" in result

    def test_preserves_meaningful_params(self):
        url = "https://example.com/search?q=python&page=3"
        result = _normalize_url(url)
        assert "q=python" in result
        assert "page=3" in result

    def test_strips_all_tracking_leaves_clean(self):
        url = "https://example.com/article?utm_source=x&fbclid=y&gclid=z"
        assert _normalize_url(url) == "https://example.com/article"

    def test_strips_fragment(self):
        # Fragments are stripped by default since urlparse separates them
        url = "https://example.com/article#section2"
        assert _normalize_url(url) == "https://example.com/article"

    def test_empty_path(self):
        assert _normalize_url("https://example.com") == "https://example.com/"

    def test_dedup_key_uses_normalized(self):
        """Two articles with same content but different tracking params should have same dedup key."""
        a1 = Article(title="Breaking News", url="https://example.com/news?utm_source=twitter", source="test")
        a2 = Article(title="Breaking News", url="https://example.com/news?utm_source=facebook", source="test")
        assert a1.dedup_key == a2.dedup_key

    def test_dedup_key_different_for_different_content(self):
        a1 = Article(title="Breaking News", url="https://example.com/news?id=1", source="test")
        a2 = Article(title="Breaking News", url="https://example.com/news?id=2", source="test")
        assert a1.dedup_key != a2.dedup_key

    def test_handles_malformed_url(self):
        assert _normalize_url("not-a-url") == "not-a-url"
