"""Tests for v5.8.0: Lemmy source, --no-lemmy flag, --only lemmy, quality weight."""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.sources.lemmy import LemmySource, _map_category


# --- Lemmy source unit tests ---

MOCK_LEMMY_RESPONSE = {
    "posts": [
        {
            "post": {
                "id": 12345,
                "name": "Rust 2.0 Released with Major Improvements",
                "url": "https://blog.rust-lang.org/2026/02/14/rust-2.html",
                "published": "2026-02-14T18:00:00Z",
            },
            "community": {
                "name": "rust",
                "title": "The Rust Programming Language",
            },
            "counts": {
                "score": 256,
                "comments": 42,
            },
            "creator": {
                "name": "rustacean",
            },
        },
        {
            "post": {
                "id": 12346,
                "name": "Self-hosted alternative to Google Photos",
                "url": None,
                "published": "2026-02-14T17:30:00Z",
            },
            "community": {
                "name": "selfhosted",
                "title": "Self-Hosted",
            },
            "counts": {
                "score": 128,
                "comments": 31,
            },
            "creator": {
                "name": "homelabber",
            },
        },
        {
            "post": {
                "id": 12347,
                "name": "",  # Empty title — should be skipped
                "url": "https://example.com",
                "published": "2026-02-14T17:00:00Z",
            },
            "community": {"name": "test", "title": "Test"},
            "counts": {"score": 1, "comments": 0},
            "creator": {"name": "bot"},
        },
    ]
}


class TestLemmySource:
    def test_crawl_parses_posts(self):
        src = LemmySource(limit=10)
        with patch.object(src, "fetch_json", return_value=MOCK_LEMMY_RESPONSE):
            # Mock to only test one instance
            from clawler.sources import lemmy
            original = lemmy.LEMMY_INSTANCES
            lemmy.LEMMY_INSTANCES = [{"url": "https://lemmy.world", "name": "lemmy.world"}]
            try:
                articles = src.crawl()
            finally:
                lemmy.LEMMY_INSTANCES = original

        # Should get 2 articles (empty title skipped)
        assert len(articles) == 2

    def test_article_fields(self):
        src = LemmySource(limit=10)
        with patch.object(src, "fetch_json", return_value=MOCK_LEMMY_RESPONSE):
            from clawler.sources import lemmy
            original = lemmy.LEMMY_INSTANCES
            lemmy.LEMMY_INSTANCES = [{"url": "https://lemmy.world", "name": "lemmy.world"}]
            try:
                articles = src.crawl()
            finally:
                lemmy.LEMMY_INSTANCES = original

        art = articles[0]
        assert art.title == "Rust 2.0 Released with Major Improvements"
        assert art.url == "https://blog.rust-lang.org/2026/02/14/rust-2.html"
        assert art.source == "Lemmy (lemmy.world)"
        assert art.author == "rustacean"
        assert art.discussion_url == "https://lemmy.world/post/12345"
        assert "lemmy:rust" in art.tags
        assert art.category == "tech"
        assert art.timestamp is not None
        assert art.timestamp.tzinfo is not None

    def test_self_post_url_fallback(self):
        """Posts without external URL should use Lemmy post page as URL."""
        src = LemmySource(limit=10)
        with patch.object(src, "fetch_json", return_value=MOCK_LEMMY_RESPONSE):
            from clawler.sources import lemmy
            original = lemmy.LEMMY_INSTANCES
            lemmy.LEMMY_INSTANCES = [{"url": "https://lemmy.world", "name": "lemmy.world"}]
            try:
                articles = src.crawl()
            finally:
                lemmy.LEMMY_INSTANCES = original

        self_post = articles[1]
        assert self_post.url == "https://lemmy.world/post/12346"

    def test_empty_response(self):
        src = LemmySource(limit=10)
        with patch.object(src, "fetch_json", return_value=None):
            from clawler.sources import lemmy
            original = lemmy.LEMMY_INSTANCES
            lemmy.LEMMY_INSTANCES = [{"url": "https://lemmy.world", "name": "lemmy.world"}]
            try:
                articles = src.crawl()
            finally:
                lemmy.LEMMY_INSTANCES = original

        assert articles == []

    def test_fetch_failure_graceful(self):
        src = LemmySource(limit=10)
        with patch.object(src, "fetch_json", side_effect=Exception("Connection refused")):
            from clawler.sources import lemmy
            original = lemmy.LEMMY_INSTANCES
            lemmy.LEMMY_INSTANCES = [{"url": "https://lemmy.world", "name": "lemmy.world"}]
            try:
                articles = src.crawl()
            finally:
                lemmy.LEMMY_INSTANCES = original

        assert articles == []

    def test_multiple_instances(self):
        src = LemmySource(limit=10)
        call_count = [0]
        def mock_fetch(url):
            call_count[0] += 1
            return MOCK_LEMMY_RESPONSE

        with patch.object(src, "fetch_json", side_effect=mock_fetch):
            from clawler.sources import lemmy
            original = lemmy.LEMMY_INSTANCES
            lemmy.LEMMY_INSTANCES = [
                {"url": "https://lemmy.world", "name": "lemmy.world"},
                {"url": "https://lemmy.ml", "name": "lemmy.ml"},
            ]
            try:
                articles = src.crawl()
            finally:
                lemmy.LEMMY_INSTANCES = original

        # 2 valid posts per instance × 2 instances = 4
        assert len(articles) == 4
        assert call_count[0] == 2

    def test_summary_contains_metadata(self):
        src = LemmySource(limit=10)
        with patch.object(src, "fetch_json", return_value=MOCK_LEMMY_RESPONSE):
            from clawler.sources import lemmy
            original = lemmy.LEMMY_INSTANCES
            lemmy.LEMMY_INSTANCES = [{"url": "https://lemmy.world", "name": "lemmy.world"}]
            try:
                articles = src.crawl()
            finally:
                lemmy.LEMMY_INSTANCES = original

        summary = articles[0].summary
        assert "Score: 256" in summary
        assert "Comments: 42" in summary
        assert "The Rust Programming Language" in summary


class TestLemmyCategoryMapping:
    def test_tech_communities(self):
        for c in ("technology", "programming", "linux", "rust", "python", "selfhosted"):
            assert _map_category(c) == "tech", f"{c} should map to tech"

    def test_science_communities(self):
        for c in ("science", "physics", "astronomy", "space"):
            assert _map_category(c) == "science", f"{c} should map to science"

    def test_world_communities(self):
        for c in ("worldnews", "news", "politics"):
            assert _map_category(c) == "world", f"{c} should map to world"

    def test_security_communities(self):
        for c in ("cybersecurity", "privacy", "netsec"):
            assert _map_category(c) == "security", f"{c} should map to security"

    def test_culture_communities(self):
        for c in ("gaming", "movies", "books", "music"):
            assert _map_category(c) == "culture", f"{c} should map to culture"

    def test_default_is_tech(self):
        assert _map_category("randomcommunity") == "tech"


class TestLemmyQualityWeight:
    def test_lemmy_weight_exists(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Lemmy")
        assert score == 0.63

    def test_lemmy_instance_weight(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Lemmy (lemmy.world)")
        assert score == 0.63


class TestLemmySourceName:
    def test_source_name(self):
        src = LemmySource()
        assert src.name == "lemmy"


class TestLemmyImport:
    def test_import_from_sources(self):
        from clawler.sources import LemmySource as LS
        assert LS is not None

    def test_in_all(self):
        from clawler import sources
        assert "LemmySource" in sources.__all__
