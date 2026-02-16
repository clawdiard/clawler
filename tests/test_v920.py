"""Tests for enhanced Dev.to source (v9.1.0 — multi-feed, filtering, rich metadata)."""
from datetime import datetime, timezone
from unittest.mock import patch, call

from clawler.sources.devto import DevToSource, _map_category, DEVTO_FEEDS

SAMPLE_ARTICLES = [
    {
        "title": "AI Agent Architectures",
        "url": "https://dev.to/alice/ai-agents",
        "description": "Deep dive into agent patterns",
        "tag_list": ["ai", "machinelearning", "python"],
        "published_at": "2026-02-15T10:00:00Z",
        "positive_reactions_count": 120,
        "comments_count": 15,
        "reading_time_minutes": 8,
        "user": {"name": "Alice", "username": "alice"},
    },
    {
        "title": "CSS Grid Tricks",
        "url": "https://dev.to/bob/css-grid",
        "description": "Modern layout techniques",
        "tag_list": ["css", "webdev", "design"],
        "published_at": "2026-02-15T09:00:00Z",
        "positive_reactions_count": 45,
        "comments_count": 3,
        "reading_time_minutes": 4,
        "user": {"name": "Bob", "username": "bob"},
    },
    {
        "title": "Solidity Smart Contracts",
        "url": "https://dev.to/carol/solidity",
        "description": "Web3 dev guide",
        "tag_list": ["blockchain", "web3"],
        "published_at": "2026-02-15T08:00:00Z",
        "positive_reactions_count": 10,
        "comments_count": 1,
        "reading_time_minutes": 6,
        "user": {"username": "carol"},
    },
]


def test_multi_feed_support():
    """Multiple feeds should be fetched with deduplication."""
    src = DevToSource(feeds=["published", "rising"], per_page=10)
    calls = []

    def mock_fetch(url):
        calls.append(url)
        return SAMPLE_ARTICLES[:2]

    with patch.object(src, "fetch_json", side_effect=mock_fetch):
        articles = src.crawl()
    # 2 feeds called
    assert len(calls) == 2
    # Deduplication: same articles in both feeds → only 2 unique
    assert len(articles) == 2


def test_min_reactions_filter():
    """Articles below min_reactions should be skipped."""
    src = DevToSource(min_reactions=50)
    with patch.object(src, "fetch_json", return_value=SAMPLE_ARTICLES):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].title == "AI Agent Architectures"


def test_min_reading_time_filter():
    """Articles below min_reading_time should be skipped."""
    src = DevToSource(min_reading_time=5)
    with patch.object(src, "fetch_json", return_value=SAMPLE_ARTICLES):
        articles = src.crawl()
    assert len(articles) == 2
    titles = {a.title for a in articles}
    assert "CSS Grid Tricks" not in titles


def test_reading_time_in_summary():
    """Summary should include reading time when enabled."""
    src = DevToSource(include_reading_time=True)
    with patch.object(src, "fetch_json", return_value=SAMPLE_ARTICLES[:1]):
        articles = src.crawl()
    assert "📖8min" in articles[0].summary


def test_comments_in_summary():
    """Summary should include comment count when enabled."""
    src = DevToSource(include_comments=True)
    with patch.object(src, "fetch_json", return_value=SAMPLE_ARTICLES[:1]):
        articles = src.crawl()
    assert "💬15" in articles[0].summary


def test_category_mapping_ai():
    assert _map_category(["ai", "python"]) == "ai"


def test_category_mapping_crypto():
    assert _map_category(["blockchain", "web3"]) == "crypto"


def test_category_mapping_design():
    assert _map_category(["css", "design"]) == "design"


def test_category_fallback_tech():
    assert _map_category(["javascript", "react"]) == "tech"


def test_category_empty_tags():
    assert _map_category([]) == "tech"


def test_tag_prefix():
    """Tags should be prefixed with devto:."""
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=SAMPLE_ARTICLES[:1]):
        articles = src.crawl()
    assert articles[0].tags == ["devto:ai", "devto:machinelearning", "devto:python"]


def test_tag_filter():
    """Single tag parameter should be passed to API."""
    src = DevToSource(tag="python")
    urls = []

    def mock_fetch(url):
        urls.append(url)
        return []

    with patch.object(src, "fetch_json", side_effect=mock_fetch):
        src.crawl()
    assert "tag=python" in urls[0]


def test_multi_tag_fetch():
    """Multiple tags should trigger separate API calls."""
    src = DevToSource(tags=["python", "rust"])
    urls = []

    def mock_fetch(url):
        urls.append(url)
        return []

    with patch.object(src, "fetch_json", side_effect=mock_fetch):
        src.crawl()
    assert len(urls) == 2
    assert any("tag=python" in u for u in urls)
    assert any("tag=rust" in u for u in urls)


def test_rising_feed_source_label():
    """Non-published feeds should have feed name in source."""
    src = DevToSource(feeds=["rising"])
    with patch.object(src, "fetch_json", return_value=SAMPLE_ARTICLES[:1]):
        articles = src.crawl()
    assert articles[0].source == "dev.to (rising)"
    assert "devto-feed:rising" in articles[0].tags


def test_top_parameter():
    """top parameter should be included in URL for published feed."""
    src = DevToSource(top=7)
    urls = []

    def mock_fetch(url):
        urls.append(url)
        return []

    with patch.object(src, "fetch_json", side_effect=mock_fetch):
        src.crawl()
    assert "top=7" in urls[0]
