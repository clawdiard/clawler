"""Tests for v4.2.0 features: Mastodon source, cache tags fix, --tag filter."""
import pytest
from datetime import datetime, timezone
from clawler.models import Article
from clawler.cache import _article_to_dict, _dict_to_article


class TestCacheTagsSerialization:
    """Verify tags field survives cache round-trip (bug fix)."""

    def test_tags_preserved_in_dict(self):
        a = Article(title="Test", url="https://example.com", source="test",
                    tags=["fediverse", "trending"])
        d = _article_to_dict(a)
        assert d["tags"] == ["fediverse", "trending"]

    def test_tags_restored_from_dict(self):
        d = {"title": "Test", "url": "https://example.com", "source": "test",
             "tags": ["ai", "ml"]}
        a = _dict_to_article(d)
        assert a.tags == ["ai", "ml"]

    def test_missing_tags_default_empty(self):
        d = {"title": "Test", "url": "https://example.com", "source": "test"}
        a = _dict_to_article(d)
        assert a.tags == []

    def test_roundtrip(self):
        original = Article(title="Story", url="https://x.com/1", source="src",
                           tags=["breaking", "tech"], quality_score=0.8,
                           timestamp=datetime(2026, 2, 14, tzinfo=timezone.utc))
        restored = _dict_to_article(_article_to_dict(original))
        assert restored.tags == original.tags
        assert restored.quality_score == original.quality_score


class TestMastodonSource:
    """Basic unit tests for the Mastodon source."""

    def test_import(self):
        from clawler.sources.mastodon import MastodonSource
        src = MastodonSource()
        assert src.name == "mastodon"
        assert len(src.instances) >= 4

    def test_guess_category_tech(self):
        from clawler.sources.mastodon import _guess_category
        assert _guess_category("New AI model released", "", "") in ("tech", "ai")

    def test_guess_category_science(self):
        from clawler.sources.mastodon import _guess_category
        assert _guess_category("Climate research study", "", "") == "science"

    def test_guess_category_security(self):
        from clawler.sources.mastodon import _guess_category
        assert _guess_category("Critical vulnerability found", "", "") == "security"

    def test_guess_category_general(self):
        from clawler.sources.mastodon import _guess_category
        assert _guess_category("Something happened today", "", "") == "general"

    def test_custom_instances(self):
        from clawler.sources.mastodon import MastodonSource
        src = MastodonSource(instances=["example.social"], limit=5)
        assert src.instances == ["example.social"]
        assert src.limit == 5


class TestTagFilter:
    """Test --tag filtering logic."""

    def test_tag_filter(self):
        articles = [
            Article(title="A", url="u1", source="s", tags=["tech", "ai"]),
            Article(title="B", url="u2", source="s", tags=["sports"]),
            Article(title="C", url="u3", source="s", tags=[]),
        ]
        tag_query = "tech"
        filtered = [a for a in articles if any(tag_query in t.lower() for t in a.tags)]
        assert len(filtered) == 1
        assert filtered[0].title == "A"

    def test_tag_filter_case_insensitive(self):
        articles = [
            Article(title="A", url="u1", source="s", tags=["Fediverse"]),
        ]
        tq = "fediverse"
        filtered = [a for a in articles if any(tq in t.lower() for t in a.tags)]
        assert len(filtered) == 1
