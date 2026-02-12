"""Test cache serialization preserves quality_score and source_count."""
from datetime import datetime, timezone
from clawler.cache import _article_to_dict, _dict_to_article
from clawler.models import Article


def test_cache_round_trip_preserves_fields():
    """quality_score and source_count should survive serialize/deserialize."""
    a = Article(
        title="Test Article",
        url="https://example.com/test",
        source="Test Source",
        summary="Summary",
        timestamp=datetime(2026, 2, 12, tzinfo=timezone.utc),
        category="tech",
        quality_score=0.85,
        source_count=3,
    )
    d = _article_to_dict(a)
    restored = _dict_to_article(d)
    assert restored.quality_score == 0.85
    assert restored.source_count == 3
    assert restored.title == "Test Article"


def test_cache_backward_compat():
    """Old cache entries without quality_score/source_count get defaults."""
    d = {
        "title": "Old Article",
        "url": "https://example.com/old",
        "source": "Old Source",
        "summary": "",
        "timestamp": None,
        "category": "general",
        "relevance": None,
    }
    restored = _dict_to_article(d)
    assert restored.quality_score == 0.5
    assert restored.source_count == 1
