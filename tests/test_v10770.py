"""Tests for v10.77.0 — quality_score propagation fixes."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.hackernews import HackerNewsSource
from clawler.sources.producthunt import ProductHuntSource


class TestHackerNewsQualityScore:
    """Verify HN source sets quality_score on Article objects."""

    def test_quality_score_set_on_article(self):
        """quality_score field should be populated, not left at default 0.5."""
        src = HackerNewsSource(feeds=["top"], limit=1)

        fake_item = {
            "type": "story",
            "id": 12345,
            "title": "Test Story About AI",
            "url": "https://example.com/ai",
            "score": 150,
            "by": "testuser",
            "descendants": 42,
            "time": 1700000000,
        }

        with patch.object(src, 'fetch_json', return_value=fake_item):
            article = src._fetch_item(12345, "top", 0)

        assert article is not None
        # quality_score should be computed and set, not the default 0.5
        assert article.quality_score != 0.5
        assert article.quality_score > 0.0
        assert article.quality_score <= 1.0

    def test_quality_score_increases_with_score(self):
        """Higher HN scores should produce higher quality_score."""
        src = HackerNewsSource(feeds=["top"], limit=1)

        def make_item(score):
            return {
                "type": "story", "id": 1, "title": "Test",
                "url": "https://example.com", "score": score,
                "by": "user", "descendants": 10, "time": 1700000000,
            }

        with patch.object(src, 'fetch_json', return_value=make_item(10)):
            low = src._fetch_item(1, "top", 0)
        with patch.object(src, 'fetch_json', return_value=make_item(1000)):
            high = src._fetch_item(1, "top", 0)

        assert high.quality_score > low.quality_score

    def test_sorting_uses_quality_score_field(self):
        """crawl() should sort by quality_score, not by parsing tag strings."""
        src = HackerNewsSource(feeds=["top"], limit=2)

        items = {
            "top": [100, 200],
            100: {"type": "story", "id": 100, "title": "Low Score",
                  "url": "https://a.com", "score": 5, "by": "u", "descendants": 0, "time": 1700000000},
            200: {"type": "story", "id": 200, "title": "High Score",
                  "url": "https://b.com", "score": 500, "by": "u", "descendants": 50, "time": 1700000000},
        }

        def fake_fetch(url):
            for key, val in items.items():
                if str(key) in url:
                    return val
            return None

        with patch.object(src, 'fetch_json', side_effect=fake_fetch):
            articles = src.crawl()

        assert len(articles) == 2
        # First article should have higher quality_score
        assert articles[0].quality_score >= articles[1].quality_score


class TestProductHuntQualityScore:
    """Verify ProductHunt source sets quality_score on Article objects."""

    def test_compute_quality_returns_valid_range(self):
        src = ProductHuntSource()
        q = src._compute_quality(0, 20, "Cool Product", "A cool thing", "maker", "tech")
        assert 0.0 <= q <= 1.0
