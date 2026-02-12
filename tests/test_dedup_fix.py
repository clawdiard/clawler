"""Tests for dedup fuzzy replacement correctness (v2.5.0 fix)."""
from clawler.dedup import deduplicate
from clawler.models import Article


class TestDedupFuzzyReplacement:
    def test_fuzzy_replacement_updates_title(self):
        """When fuzzy match replaces an article, future comparisons use the new title."""
        a1 = Article(title="Major earthquake strikes California coast today",
                     url="https://a.com/1", source="low", quality_score=0.3)
        a2 = Article(title="Major earthquake strikes California coast",
                     url="https://b.com/1", source="high", quality_score=0.9)
        # Third article is similar to a2's title (which replaced a1)
        a3 = Article(title="Major earthquake strikes California coast tonight",
                     url="https://c.com/1", source="mid", quality_score=0.5)

        result = deduplicate([a1, a2, a3], similarity_threshold=0.75)
        # Should have exactly 1 article — the highest quality one
        assert len(result) == 1
        assert result[0].source == "high"

    def test_fuzzy_replacement_updates_fingerprint(self):
        """When fuzzy match replaces, new fingerprint should be indexed."""
        a1 = Article(title="Python release candidate announced",
                     url="https://a.com/1", source="low", quality_score=0.3)
        a2 = Article(title="Python release candidate announced today",
                     url="https://b.com/1", source="high", quality_score=0.9)

        result = deduplicate([a1, a2], similarity_threshold=0.75)
        assert len(result) == 1
        assert result[0].source == "high"

    def test_quality_aware_keeps_higher(self):
        """Dedup always keeps the higher-quality version."""
        low = Article(title="AI breakthrough in medicine", url="https://a.com/1",
                      source="blog", quality_score=0.4)
        high = Article(title="AI breakthrough in medicine", url="https://b.com/1",
                       source="Nature", quality_score=0.9)
        result = deduplicate([low, high])
        assert len(result) == 1
        assert result[0].source == "Nature"
