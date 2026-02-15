"""Tests for Hacker News source."""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from clawler.sources.hackernews import HackerNewsSource, _detect_category


def test_detect_category_ai():
    assert _detect_category("GPT-5 released by OpenAI", "https://openai.com") == "ai"


def test_detect_category_security():
    assert _detect_category("New zero-day vulnerability in Linux kernel", "https://cve.org") == "security"


def test_detect_category_programming():
    assert _detect_category("Rust 2.0 released with new compiler", "https://rust-lang.org") == "programming"


def test_detect_category_business():
    assert _detect_category("Startup raises Series A funding", "https://techcrunch.com") == "business"


def test_detect_category_science():
    assert _detect_category("NASA discovers new exoplanet", "https://nasa.gov") == "science"


def test_detect_category_default():
    assert _detect_category("Something happened today", "https://example.com") == "tech"


def test_hackernews_crawl_basic():
    """Test HN source fetches and parses stories correctly."""
    src = HackerNewsSource(feeds=["top"], limit=2, max_workers=1)

    fake_item = {
        "type": "story",
        "title": "Test Story About AI",
        "url": "https://example.com/ai-story",
        "by": "testuser",
        "score": 150,
        "descendants": 42,
        "time": 1739600000,
    }

    def mock_fetch_json(url):
        if "topstories" in url:
            return [1001, 1002]
        if "item/1001" in url:
            return fake_item
        if "item/1002" in url:
            return {**fake_item, "title": "Second Story", "url": "https://example.com/second", "score": 50}
        return None

    with patch.object(src, "fetch_json", side_effect=mock_fetch_json):
        articles = src.crawl()

    assert len(articles) == 2
    assert articles[0].source.startswith("Hacker News")
    assert articles[0].author == "testuser"
    assert articles[0].discussion_url.startswith("https://news.ycombinator.com/item?id=")
    assert articles[0].timestamp is not None


def test_hackernews_min_score_filter():
    """Test that min_score filters out low-score stories."""
    src = HackerNewsSource(feeds=["top"], limit=2, min_score=100, max_workers=1)

    def mock_fetch_json(url):
        if "topstories" in url:
            return [1001, 1002]
        if "item/1001" in url:
            return {"type": "story", "title": "High Score", "url": "https://a.com", "by": "u", "score": 200, "descendants": 10, "time": 1739600000}
        if "item/1002" in url:
            return {"type": "story", "title": "Low Score", "url": "https://b.com", "by": "u", "score": 30, "descendants": 1, "time": 1739600000}
        return None

    with patch.object(src, "fetch_json", side_effect=mock_fetch_json):
        articles = src.crawl()

    assert len(articles) == 1
    assert articles[0].title == "High Score"


def test_hackernews_multi_feed_dedup():
    """Test that stories appearing in multiple feeds are deduplicated."""
    src = HackerNewsSource(feeds=["top", "best"], limit=2, max_workers=1)

    def mock_fetch_json(url):
        if "topstories" in url:
            return [1001, 1002]
        if "beststories" in url:
            return [1001, 1003]  # 1001 is duplicate
        if "item/" in url:
            sid = int(url.split("/")[-1].replace(".json", ""))
            return {"type": "story", "title": f"Story {sid}", "url": f"https://ex.com/{sid}", "by": "u", "score": 100, "descendants": 5, "time": 1739600000}
        return None

    with patch.object(src, "fetch_json", side_effect=mock_fetch_json):
        articles = src.crawl()

    # 1001, 1002, 1003 = 3 unique stories
    assert len(articles) == 3


def test_hackernews_empty_feed():
    """Test handling of empty/failed feed response."""
    src = HackerNewsSource(feeds=["top"], limit=5, max_workers=1)
    with patch.object(src, "fetch_json", return_value=None):
        articles = src.crawl()
    assert articles == []


def test_hackernews_ask_prefix():
    """Test that Ask HN stories get proper prefix handling."""
    src = HackerNewsSource(feeds=["ask"], limit=1, max_workers=1)

    def mock_fetch_json(url):
        if "askstories" in url:
            return [1001]
        return {"type": "story", "title": "How do you deploy?", "url": "", "by": "u", "score": 50, "descendants": 20, "time": 1739600000}

    with patch.object(src, "fetch_json", side_effect=mock_fetch_json):
        articles = src.crawl()

    assert len(articles) == 1
    assert articles[0].title.startswith("Ask HN: ")
