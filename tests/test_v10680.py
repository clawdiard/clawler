"""Tests for HackerNews v10.68.0 quality scoring enhancements."""
from unittest.mock import patch, MagicMock
from clawler.sources.hackernews import (
    HackerNewsSource, _detect_category, _score_to_quality,
    _comment_engagement, FEED_PROMINENCE, PROMINENT_AUTHORS,
)


class TestHNQualityScoring:
    """Test quality scoring components."""

    def test_score_to_quality_zero(self):
        assert _score_to_quality(0) == 0.0

    def test_score_to_quality_low(self):
        q = _score_to_quality(10)
        assert 0.05 < q < 0.15

    def test_score_to_quality_high(self):
        q = _score_to_quality(1000)
        assert q >= 0.25

    def test_score_to_quality_capped(self):
        q = _score_to_quality(100000)
        assert q <= 0.40

    def test_comment_engagement_none(self):
        assert _comment_engagement(0, 100) == 0.0
        assert _comment_engagement(10, 0) == 0.0

    def test_comment_engagement_high(self):
        q = _comment_engagement(200, 100)
        assert q > 0.0

    def test_detect_category_ai(self):
        assert _detect_category("GPT-5 released today", "https://openai.com") == "ai"

    def test_detect_category_security(self):
        assert _detect_category("Critical vulnerability found in SSH", "https://example.com") == "security"

    def test_detect_category_devops(self):
        assert _detect_category("Kubernetes 2.0 announced", "https://k8s.io") == "devops"

    def test_detect_category_culture(self):
        assert _detect_category("The best philosophy books of 2026", "https://books.com") == "culture"

    def test_detect_category_default(self):
        assert _detect_category("Something random", "https://example.com") == "tech"

    def test_feed_prominence_keys(self):
        for feed in ("top", "best", "new", "ask", "show", "job"):
            assert feed in FEED_PROMINENCE

    def test_prominent_authors_are_lowercase(self):
        for author in PROMINENT_AUTHORS:
            assert author == author.lower()


class TestHNSourceInit:
    """Test source initialization and parameters."""

    def test_defaults(self):
        s = HackerNewsSource()
        assert s.feeds == ["top"]
        assert s.limit == 30
        assert s.min_score == 0
        assert s.min_quality == 0.0
        assert s.category_filter is None

    def test_custom_params(self):
        s = HackerNewsSource(feeds=["best", "ask"], limit=10, min_quality=0.3,
                             category_filter=["ai", "security"])
        assert s.feeds == ["best", "ask"]
        assert s.min_quality == 0.3
        assert s.category_filter == ["ai", "security"]

    def test_compute_quality_range(self):
        s = HackerNewsSource()
        q = s._compute_quality(score=500, comments=200, author="pg",
                               feed_type="best", position=0)
        assert 0.0 <= q <= 1.0
        assert q > 0.5  # High-quality story from prominent author

    def test_compute_quality_low(self):
        s = HackerNewsSource()
        q = s._compute_quality(score=1, comments=0, author="nobody",
                               feed_type="new", position=29)
        assert q < 0.3

    def test_compute_quality_prominent_author_boost(self):
        s = HackerNewsSource()
        q_nobody = s._compute_quality(100, 50, "nobody", "top", 5)
        q_pg = s._compute_quality(100, 50, "pg", "top", 5)
        assert q_pg > q_nobody


class TestProductHuntQuality:
    """Test ProductHunt quality scoring."""

    def test_import(self):
        from clawler.sources.producthunt import ProductHuntSource, PROMINENT_HUNTERS
        assert len(PROMINENT_HUNTERS) > 0

    def test_quality_range(self):
        from clawler.sources.producthunt import ProductHuntSource
        s = ProductHuntSource()
        q = s._compute_quality(0, 50, "AI Code Editor", "AI-powered coding", "rrhoover", "ai")
        assert 0.0 <= q <= 1.0
        assert q > 0.5  # Top position + prominent hunter + good keywords

    def test_quality_min_filter(self):
        from clawler.sources.producthunt import ProductHuntSource
        s = ProductHuntSource(min_quality=0.9)
        assert s.min_quality == 0.9


class TestNewRSSFeeds:
    """Test new RSS feed categories added in v10.68.0."""

    def test_new_categories_present(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        categories = {f["category"] for f in DEFAULT_FEEDS}
        for cat in ("sleep_science", "sound_design", "solarpunk", "mycology"):
            assert cat in categories, f"Missing category: {cat}"

    def test_new_feed_count(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        new_cats = {"sleep_science", "sound_design", "solarpunk", "mycology"}
        new_feeds = [f for f in DEFAULT_FEEDS if f["category"] in new_cats]
        assert len(new_feeds) >= 18

    def test_feed_urls_are_strings(self):
        from clawler.sources.rss import DEFAULT_FEEDS
        for f in DEFAULT_FEEDS:
            assert isinstance(f["url"], str)
            assert f["url"].startswith("http")
