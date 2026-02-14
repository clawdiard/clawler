"""Tests for v5.3.0 — Bluesky source."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.sources.bluesky import BlueskySource, _guess_category
from clawler.models import Article


def _make_feed_response(posts):
    """Build a mock Bluesky feed API response."""
    feed = []
    for p in posts:
        feed.append({
            "post": {
                "uri": p.get("uri", "at://did:plc:abc123/app.bsky.feed.post/xyz789"),
                "author": {
                    "handle": p.get("handle", "user.bsky.social"),
                    "displayName": p.get("display_name", "Test User"),
                },
                "record": {
                    "createdAt": p.get("created_at", "2026-02-14T12:00:00Z"),
                    "text": p.get("text", "Check this out"),
                },
                "embed": {
                    "$type": "app.bsky.embed.external#view",
                    "external": {
                        "uri": p.get("url", "https://example.com/article"),
                        "title": p.get("title", "Test Article"),
                        "description": p.get("description", "A test description"),
                    },
                },
                "likeCount": p.get("likes", 10),
                "repostCount": p.get("reposts", 5),
                "replyCount": p.get("replies", 2),
            }
        })
    return {"feed": feed}


class TestBlueskySource:
    """Tests for BlueskySource."""

    def test_init_defaults(self):
        src = BlueskySource()
        assert src.name == "bluesky"
        assert src.limit == 40

    def test_init_custom_limit(self):
        src = BlueskySource(limit=10)
        assert src.limit == 10

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_returns_articles(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {"title": "AI Breakthrough", "url": "https://example.com/ai", "description": "New AI model released"},
            {"title": "Rust 2.0", "url": "https://example.com/rust", "description": "Rust programming language update"},
        ])
        src = BlueskySource()
        articles = src.crawl()
        assert len(articles) >= 2
        assert all(isinstance(a, Article) for a in articles)
        assert articles[0].title == "AI Breakthrough"
        assert articles[0].source == "Bluesky"

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_deduplicates_urls(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {"title": "Same Article", "url": "https://example.com/same"},
            {"title": "Same Article Copy", "url": "https://example.com/same"},
        ])
        src = BlueskySource()
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert urls.count("https://example.com/same") == 1

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_skips_bsky_internal_links(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {"title": "Internal", "url": "https://bsky.app/profile/someone"},
            {"title": "External", "url": "https://example.com/real"},
        ])
        src = BlueskySource()
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].url == "https://example.com/real"

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_skips_no_title(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {"title": "", "url": "https://example.com/notitle"},
            {"title": "Has Title", "url": "https://example.com/good"},
        ])
        src = BlueskySource()
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].title == "Has Title"

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_empty_response(self, mock_fetch):
        mock_fetch.return_value = None
        src = BlueskySource()
        articles = src.crawl()
        assert articles == []

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_no_feed_key(self, mock_fetch):
        mock_fetch.return_value = {"error": "not found"}
        src = BlueskySource()
        articles = src.crawl()
        assert articles == []

    @patch.object(BlueskySource, "fetch_json")
    def test_article_has_discussion_url(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {
                "title": "Discussion Test",
                "url": "https://example.com/discuss",
                "handle": "alice.bsky.social",
                "uri": "at://did:plc:abc123/app.bsky.feed.post/rkey999",
            },
        ])
        src = BlueskySource()
        articles = src.crawl()
        assert len(articles) == 1
        assert articles[0].discussion_url == "https://bsky.app/profile/alice.bsky.social/post/rkey999"

    @patch.object(BlueskySource, "fetch_json")
    def test_article_has_author(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {"title": "Author Test", "url": "https://example.com/auth", "display_name": "Jane Doe"},
        ])
        src = BlueskySource()
        articles = src.crawl()
        assert articles[0].author == "Jane Doe"

    @patch.object(BlueskySource, "fetch_json")
    def test_article_tags(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {"title": "Tag Test", "url": "https://example.com/tags"},
        ])
        src = BlueskySource()
        articles = src.crawl()
        assert "bluesky" in articles[0].tags
        assert "social" in articles[0].tags

    @patch.object(BlueskySource, "fetch_json")
    def test_timestamp_parsed(self, mock_fetch):
        mock_fetch.return_value = _make_feed_response([
            {"title": "Time Test", "url": "https://example.com/time", "created_at": "2026-02-14T10:30:00Z"},
        ])
        src = BlueskySource()
        articles = src.crawl()
        assert articles[0].timestamp is not None
        assert articles[0].timestamp.year == 2026


class TestBlueskyCategory:
    """Tests for _guess_category helper."""

    def test_tech_category(self):
        assert _guess_category("New AI model released", "open source LLM") == "tech"

    def test_science_category(self):
        assert _guess_category("New climate research", "scientists discover") == "science"

    def test_business_category(self):
        assert _guess_category("Stock market rally", "economy grows") == "business"

    def test_security_category(self):
        assert _guess_category("Critical vulnerability found", "CVE-2026") == "security"

    def test_investigative_category(self):
        assert _guess_category("Leaked documents reveal corruption", "") == "investigative"

    def test_general_fallback(self):
        assert _guess_category("Nice weather today", "sunny skies") == "general"


class TestBlueskyAPIIntegration:
    """Test Bluesky in the crawl API."""

    def test_no_bluesky_flag(self):
        from clawler.api import crawl
        # Just verify no_bluesky param exists and doesn't crash
        # (actual crawl would hit network, so we mock)
        with patch.object(BlueskySource, "crawl", return_value=[]):
            result = crawl(no_bluesky=True, limit=1, no_rss=True, no_hn=True,
                          no_reddit=True, no_github=True, no_mastodon=True,
                          no_wikipedia=True, no_lobsters=True, no_devto=True,
                          no_arxiv=True, no_techmeme=True, no_producthunt=True)
            assert result == []
