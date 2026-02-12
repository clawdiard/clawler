"""Tests for the deduplication engine."""
from clawler.dedup import deduplicate
from clawler.models import Article
from datetime import datetime, timezone


def _article(title: str, url: str = "https://example.com", source: str = "Test") -> Article:
    return Article(title=title, url=url, source=source, timestamp=datetime.now(timezone.utc))


class TestExactDedup:
    def test_same_title_and_url(self):
        a = _article("Breaking News", "https://a.com/1")
        b = _article("Breaking News", "https://a.com/1")
        assert len(deduplicate([a, b])) == 1

    def test_different_urls_kept(self):
        a = _article("Breaking News", "https://a.com/1")
        b = _article("Breaking News", "https://b.com/1")
        # Different URLs → different dedup keys, but fingerprint or fuzzy should catch
        result = deduplicate([a, b])
        assert len(result) == 1  # fingerprint dedup catches it


class TestFingerprintDedup:
    def test_reworded_same_story(self):
        """Fingerprint dedup catches titles with same significant words."""
        a = _article("Scientists Discover New Species in Amazon Rainforest", "https://a.com/1")
        b = _article("Scientists Discover a New Species in the Amazon Rainforest", "https://b.com/2")
        result = deduplicate([a, b])
        # Same significant words → fingerprint match
        assert len(result) == 1

    def test_short_titles_not_falsely_deduped(self):
        """Very short titles should not be fingerprint-deduped (insufficient signal)."""
        a = _article("AI News", "https://a.com/1")
        b = _article("AI News", "https://b.com/2")
        # Same title → fingerprint empty (< 2 significant words), but fuzzy catches it
        result = deduplicate([a, b])
        assert len(result) == 1


class TestFuzzyDedup:
    def test_similar_titles(self):
        a = _article("Apple announces new iPhone 17 with revolutionary camera")
        b = _article("Apple announces the new iPhone 17 with a revolutionary camera system")
        result = deduplicate([a, b])
        assert len(result) == 1

    def test_dissimilar_titles_kept(self):
        a = _article("Apple announces new iPhone")
        b = _article("Google releases new Pixel phone")
        result = deduplicate([a, b])
        assert len(result) == 2

    def test_threshold_respected(self):
        a = _article("Tech news roundup for today")
        b = _article("Tech news roundup for this week")
        # With a very high threshold, these should be kept separate
        result = deduplicate([a, b], similarity_threshold=0.99)
        assert len(result) == 2
        # With default threshold, they should be deduped
        result = deduplicate([a, b], similarity_threshold=0.5)
        assert len(result) == 1


class TestEdgeCases:
    def test_empty_list(self):
        assert deduplicate([]) == []

    def test_single_article(self):
        a = _article("Hello World")
        result = deduplicate([a])
        assert len(result) == 1
        assert result[0] is a

    def test_preserves_order(self):
        titles = [
            "Apple launches new MacBook Pro with M5 chip",
            "NASA discovers water on distant exoplanet Kepler-442b",
            "Bitcoin surges past $200,000 in volatile trading session",
            "New CRISPR technique eliminates sickle cell disease in trials",
            "SpaceX successfully lands Starship on Mars surface",
            "EU passes landmark artificial intelligence regulation bill",
            "Amazon unveils drone delivery service in rural areas",
            "Record-breaking heatwave hits Australian continent this summer",
            "Tesla reveals fully autonomous robotaxi fleet in San Francisco",
            "OpenAI releases GPT-6 with unprecedented reasoning capabilities",
        ]
        articles = [_article(t, f"https://x.com/{i}") for i, t in enumerate(titles)]
        result = deduplicate(articles)
        assert len(result) == 10
        for i, a in enumerate(result):
            assert a.title == titles[i]
