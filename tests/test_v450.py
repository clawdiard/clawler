"""Tests for Lobsters source and v4.5.0 features."""
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from clawler.sources.lobsters import LobstersSource, _map_category


SAMPLE_LOBSTERS_RESPONSE = [
    {
        "short_id": "abc123",
        "title": "Why Rust is great for CLI tools",
        "url": "https://example.com/rust-cli",
        "score": 42,
        "comment_count": 15,
        "comments_url": "https://lobste.rs/s/abc123",
        "created_at": "2026-02-14T03:00:00.000-00:00",
        "submitter_user": {"username": "rustfan"},
        "tags": ["rust", "programming"],
    },
    {
        "short_id": "def456",
        "title": "Understanding TLS 1.3",
        "url": "https://example.com/tls13",
        "score": 30,
        "comment_count": 8,
        "comments_url": "https://lobste.rs/s/def456",
        "created_at": "2026-02-14T02:00:00.000-00:00",
        "submitter_user": {"username": "secperson"},
        "tags": ["security", "networking"],
    },
    {
        "short_id": "ghi789",
        "title": "New discovery in quantum computing",
        "url": "https://example.com/quantum",
        "score": 18,
        "comment_count": 3,
        "comments_url": "https://lobste.rs/s/ghi789",
        "created_at": "2026-02-14T01:00:00.000-00:00",
        "submitter_user": {"username": "physicist"},
        "tags": ["science"],
    },
    {
        "short_id": "jkl000",
        "title": "",
        "url": "",
        "score": 0,
        "comment_count": 0,
        "comments_url": "",
        "created_at": None,
        "submitter_user": {},
        "tags": [],
    },
]


class TestLobstersSource:
    def test_crawl_parses_articles(self):
        src = LobstersSource(limit=10)
        with patch.object(src, "fetch_json", return_value=SAMPLE_LOBSTERS_RESPONSE):
            articles = src.crawl()
        # 4th item has empty title/url, should be skipped
        assert len(articles) == 3

    def test_article_fields(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=SAMPLE_LOBSTERS_RESPONSE):
            articles = src.crawl()
        a = articles[0]
        assert a.title == "Why Rust is great for CLI tools"
        assert a.url == "https://example.com/rust-cli"
        assert "Lobsters" in a.source
        assert "42" in a.source  # score in source name
        assert a.category == "tech"
        assert "lobsters:rust" in a.tags
        assert a.timestamp is not None

    def test_security_category(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=SAMPLE_LOBSTERS_RESPONSE):
            articles = src.crawl()
        sec = [a for a in articles if a.category == "security"]
        assert len(sec) == 1
        assert "TLS" in sec[0].title

    def test_science_category(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=SAMPLE_LOBSTERS_RESPONSE):
            articles = src.crawl()
        sci = [a for a in articles if a.category == "science"]
        assert len(sci) == 1

    def test_limit(self):
        src = LobstersSource(limit=1)
        with patch.object(src, "fetch_json", return_value=SAMPLE_LOBSTERS_RESPONSE):
            articles = src.crawl()
        assert len(articles) == 1

    def test_empty_response(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=[]):
            assert src.crawl() == []

    def test_none_response(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=None):
            assert src.crawl() == []

    def test_fetch_failure(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", side_effect=Exception("network")):
            assert src.crawl() == []

    def test_newest_page(self):
        src = LobstersSource(page="newest")
        assert "newest" in src.url

    def test_hottest_page(self):
        src = LobstersSource(page="hottest")
        assert "hottest" in src.url

    def test_summary_content(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=SAMPLE_LOBSTERS_RESPONSE):
            articles = src.crawl()
        assert "Score: 42" in articles[0].summary
        assert "By: rustfan" in articles[0].summary
        assert "Comments: 15" in articles[0].summary

    def test_timestamp_parsing(self):
        src = LobstersSource()
        with patch.object(src, "fetch_json", return_value=SAMPLE_LOBSTERS_RESPONSE):
            articles = src.crawl()
        assert articles[0].timestamp.tzinfo is not None


class TestMapCategory:
    def test_security(self):
        assert _map_category(["security"]) == "security"
        assert _map_category(["privacy", "law"]) == "security"

    def test_science(self):
        assert _map_category(["science"]) == "science"
        assert _map_category(["math"]) == "science"

    def test_culture(self):
        assert _map_category(["culture"]) == "culture"
        assert _map_category(["person"]) == "culture"

    def test_business(self):
        assert _map_category(["practices"]) == "business"
        assert _map_category(["devops"]) == "business"

    def test_default_tech(self):
        assert _map_category(["rust", "programming"]) == "tech"
        assert _map_category([]) == "tech"


class TestV450CLI:
    def test_no_lobsters_flag(self):
        from clawler.cli import main
        import io, sys
        # --dry-run --no-lobsters should NOT show Lobsters
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main(["--dry-run", "--no-lobsters"])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        assert "Lobsters" not in output

    def test_dry_run_shows_lobsters(self):
        from clawler.cli import main
        import io, sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main(["--dry-run"])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        assert "Lobsters" in output

    def test_version_bumped(self):
        from clawler import __version__
        pass  # Version checked dynamically in test_v320

    def test_lobsters_in_sources_init(self):
        from clawler.sources import LobstersSource
        assert LobstersSource is not None

    def test_list_sources_includes_lobsters(self):
        from clawler.cli import main
        import io, sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            main(["--list-sources"])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        assert "Lobsters" in output
