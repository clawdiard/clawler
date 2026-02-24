"""Tests for Dev.to quality scoring and filtering."""
from unittest.mock import patch
from clawler.sources.devto import DevToSource, _compute_quality, PROMINENT_AUTHORS


def _make_item(title="Test Post", reactions=50, comments=10, reading_time=5,
               tags=None, author="testuser"):
    return {
        "title": title,
        "url": f"https://dev.to/{author}/{title.lower().replace(' ', '-')}",
        "description": "A test post",
        "positive_reactions_count": reactions,
        "comments_count": comments,
        "reading_time_minutes": reading_time,
        "tag_list": tags or ["python"],
        "published_at": "2026-02-24T01:00:00Z",
        "user": {"name": author, "username": author},
    }


def test_quality_score_range():
    """Quality scores should always be 0–1."""
    assert 0 <= _compute_quality(0, 0, 0, "published", "") <= 1
    assert 0 <= _compute_quality(1000, 500, 20, "rising", "ben") <= 1
    assert 0 <= _compute_quality(1, 0, 1, "latest", "") <= 1


def test_quality_increases_with_reactions():
    q_low = _compute_quality(5, 0, 3, "published", "")
    q_high = _compute_quality(500, 0, 3, "published", "")
    assert q_high > q_low


def test_quality_increases_with_comments():
    q_low = _compute_quality(50, 1, 3, "published", "")
    q_high = _compute_quality(50, 100, 3, "published", "")
    assert q_high > q_low


def test_reading_time_bonus():
    q_short = _compute_quality(50, 5, 1, "published", "")
    q_long = _compute_quality(50, 5, 10, "published", "")
    assert q_long > q_short


def test_prominent_author_boost():
    q_unknown = _compute_quality(50, 5, 3, "published", "randomuser")
    q_known = _compute_quality(50, 5, 3, "published", "ben")
    assert q_known > q_unknown


def test_rising_feed_prominence():
    q_published = _compute_quality(50, 5, 3, "published", "")
    q_rising = _compute_quality(50, 5, 3, "rising", "")
    assert q_rising > q_published


def test_quality_in_crawl_output():
    src = DevToSource()
    items = [_make_item(reactions=100, comments=20)]
    with patch.object(src, "fetch_json", return_value=items):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].quality_score is not None
    assert articles[0].quality_score > 0
    assert any("devto:quality:" in t for t in articles[0].tags)


def test_min_quality_filter():
    src = DevToSource(min_quality=0.99)
    items = [_make_item(reactions=5, comments=1)]
    with patch.object(src, "fetch_json", return_value=items):
        articles = src.crawl()
    assert len(articles) == 0


def test_category_filter():
    src = DevToSource(category_filter=["ai"])
    items = [_make_item(tags=["python"])]  # maps to 'tech', not 'ai'
    with patch.object(src, "fetch_json", return_value=items):
        articles = src.crawl()
    assert len(articles) == 0


def test_quality_sorted_output():
    src = DevToSource()
    items = [
        _make_item(title="Low", reactions=2, comments=0),
        _make_item(title="High", reactions=500, comments=100),
    ]
    with patch.object(src, "fetch_json", return_value=items):
        articles = src.crawl()
    assert len(articles) == 2
    assert articles[0].title == "High"
    assert articles[0].quality_score >= articles[1].quality_score
