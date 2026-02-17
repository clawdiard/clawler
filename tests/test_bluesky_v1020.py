"""Tests for Bluesky source v10.2.0 enhancements."""
import math
from unittest.mock import patch, MagicMock

import pytest

from clawler.sources.bluesky import (
    BlueskySource,
    _guess_category,
    _quality_score,
    _format_count,
    SPECIFIC_KEYWORDS,
)


# --- Helper to build mock post data ---

def _make_post(title, url, description="", likes=10, reposts=2, replies=1,
               handle="user.bsky.social", display_name="User", text="",
               created_at="2026-02-17T00:00:00Z"):
    return {
        "post": {
            "uri": f"at://did:plc:abc123/app.bsky.feed.post/xyz",
            "author": {"handle": handle, "displayName": display_name},
            "record": {"createdAt": created_at, "text": text},
            "embed": {
                "$type": "app.bsky.embed.external#view",
                "external": {"uri": url, "title": title, "description": description},
            },
            "likeCount": likes,
            "repostCount": reposts,
            "replyCount": replies,
        }
    }


class TestQualityScore:
    def test_zero_engagement(self):
        assert _quality_score(0, 0, 0) == 0.0

    def test_moderate_engagement(self):
        # likes=50, reposts=10, replies=10 → total = 50+30+20 = 100 → log10(100)/4 = 0.5
        score = _quality_score(50, 10, 10)
        assert 0.45 <= score <= 0.55

    def test_high_engagement(self):
        score = _quality_score(5000, 1000, 500)
        assert score >= 0.8

    def test_capped_at_one(self):
        score = _quality_score(100000, 50000, 20000)
        assert score <= 1.0


class TestFormatCount:
    def test_small(self):
        assert _format_count(500) == "500"

    def test_thousands(self):
        assert _format_count(1500) == "1.5K"

    def test_millions(self):
        assert _format_count(2300000) == "2.3M"


class TestCategoryDetection:
    def test_ai_keywords(self):
        assert _guess_category("New LLM benchmark released", "") == "ai"
        assert _guess_category("OpenAI launches GPT-5", "") == "ai"

    def test_security_keywords(self):
        assert _guess_category("Critical CVE-2026-1234 vulnerability found", "") == "security"

    def test_crypto_keywords(self):
        assert _guess_category("Bitcoin hits new all-time high", "") == "crypto"

    def test_science_keywords(self):
        assert _guess_category("NASA discovers new exoplanet", "") == "science"

    def test_health_keywords(self):
        assert _guess_category("FDA approves new cancer drug", "") == "health"

    def test_business_keywords(self):
        assert _guess_category("Tech IPO raises $2B", "") == "business"

    def test_design_keywords(self):
        assert _guess_category("New Figma features for UX designers", "") == "design"

    def test_gaming_keywords(self):
        assert _guess_category("Nintendo announces new console", "") == "gaming"

    def test_generic_tech_fallback(self):
        assert _guess_category("New Python library for developers", "") == "tech"

    def test_general_fallback(self):
        assert _guess_category("My cat is cute", "") == "general"

    def test_specific_over_generic(self):
        # "ai" should win over generic "tech" even though "developer" is present
        assert _guess_category("AI developer builds new LLM tool", "") == "ai"


class TestBlueskyExtraction:
    def _run_extract(self, feed_items, **kwargs):
        src = BlueskySource(**kwargs)
        articles = []
        seen = set()
        src._extract_posts(feed_items, articles, seen)
        return articles

    def test_basic_extraction(self):
        items = [_make_post("Test Article", "https://example.com/article")]
        articles = self._run_extract(items)
        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        assert articles[0].url == "https://example.com/article"
        assert articles[0].source == "Bluesky"

    def test_deduplication(self):
        items = [
            _make_post("Article 1", "https://example.com/same"),
            _make_post("Article 2", "https://example.com/same"),
        ]
        articles = self._run_extract(items)
        assert len(articles) == 1

    def test_skip_bsky_internal(self):
        items = [_make_post("Bsky Post", "https://bsky.app/something")]
        articles = self._run_extract(items)
        assert len(articles) == 0

    def test_skip_no_title(self):
        items = [_make_post("", "https://example.com/no-title")]
        articles = self._run_extract(items)
        assert len(articles) == 0

    def test_min_likes_filter(self):
        items = [_make_post("Low Likes", "https://example.com/low", likes=3)]
        articles = self._run_extract(items, min_likes=5)
        assert len(articles) == 0

    def test_min_engagement_filter(self):
        items = [_make_post("Low Eng", "https://example.com/low", likes=1, reposts=0, replies=0)]
        articles = self._run_extract(items, min_engagement=10)
        assert len(articles) == 0

    def test_exclude_domains(self):
        items = [_make_post("Blocked", "https://spam.com/article")]
        articles = self._run_extract(items, exclude_domains=["spam.com"])
        assert len(articles) == 0

    def test_quality_score_set(self):
        items = [_make_post("Quality", "https://example.com/q", likes=100, reposts=50, replies=20)]
        articles = self._run_extract(items)
        assert articles[0].quality_score > 0

    def test_hashtag_extraction(self):
        items = [_make_post("Hash", "https://example.com/h", text="Check this #AI #tech post")]
        articles = self._run_extract(items)
        tags = articles[0].tags
        assert "bsky:hashtag:ai" in tags
        assert "bsky:hashtag:tech" in tags

    def test_author_in_tags(self):
        items = [_make_post("Auth", "https://example.com/a", handle="alice.bsky.social")]
        articles = self._run_extract(items)
        assert "bsky:author:alice.bsky.social" in [t for t in articles[0].tags]

    def test_discussion_url(self):
        items = [_make_post("Disc", "https://example.com/d", handle="bob.bsky.social")]
        articles = self._run_extract(items)
        assert "bsky.app/profile/bob.bsky.social/post/" in articles[0].discussion_url

    def test_recordwithmedia_embed(self):
        """Test extraction from recordWithMedia embed type."""
        item = {
            "post": {
                "uri": "at://did:plc:abc/app.bsky.feed.post/xyz",
                "author": {"handle": "user.bsky.social", "displayName": "User"},
                "record": {"createdAt": "2026-02-17T00:00:00Z", "text": ""},
                "embed": {
                    "$type": "app.bsky.embed.recordWithMedia#view",
                    "media": {
                        "$type": "app.bsky.embed.external#view",
                        "external": {"uri": "https://example.com/media", "title": "Media Post", "description": ""},
                    },
                },
                "likeCount": 5, "repostCount": 1, "replyCount": 0,
            }
        }
        articles = self._run_extract([item])
        assert len(articles) == 1
        assert articles[0].title == "Media Post"


class TestBlueskySourceCrawl:
    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_feeds_and_search(self, mock_fetch):
        """Test that crawl hits feeds and search endpoints."""
        feed_data = {"feed": [_make_post("Feed Article", "https://example.com/feed")]}
        search_data = {"posts": [_make_post("Search Article", "https://example.com/search")["post"]]}
        trending_data = {"suggestions": [{"tag": "trending_topic"}]}

        def side_effect(url):
            if "getFeed" in url:
                return feed_data
            if "searchPosts" in url:
                return search_data
            if "getTaggedSuggestions" in url:
                return trending_data
            return None

        mock_fetch.side_effect = side_effect
        src = BlueskySource(limit=50, include_trending=True)
        articles = src.crawl()
        assert len(articles) >= 1
        # Should have called getFeed, getTaggedSuggestions, and searchPosts
        assert mock_fetch.call_count >= 3

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_respects_limit(self, mock_fetch):
        posts = [_make_post(f"Art {i}", f"https://example.com/{i}", likes=100-i) for i in range(20)]
        mock_fetch.return_value = {"feed": posts}

        src = BlueskySource(limit=5, feeds=["whats-hot"], search_queries=[], include_trending=False)
        articles = src.crawl()
        assert len(articles) <= 5

    @patch.object(BlueskySource, "fetch_json")
    def test_crawl_sorts_by_quality(self, mock_fetch):
        posts = [
            _make_post("Low", "https://example.com/low", likes=1),
            _make_post("High", "https://example.com/high", likes=5000, reposts=1000),
        ]
        mock_fetch.return_value = {"feed": posts}

        src = BlueskySource(limit=50, feeds=["whats-hot"], search_queries=[], include_trending=False)
        articles = src.crawl()
        assert articles[0].title == "High"
