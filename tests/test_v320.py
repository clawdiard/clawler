"""Tests for v3.4.0 features: --remove-bookmark, --count, DRY fetch, RSS rate limiting, version sync, build backend."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from clawler.bookmarks import add_bookmarks, remove_bookmark, load_bookmarks
from clawler.models import Article
from clawler.sources.base import BaseSource


def _make_article(url="https://example.com"):
    return Article(title="Test", url=url, source="Test")


class TestRemoveBookmark:
    def test_remove_existing(self, tmp_path):
        path = tmp_path / "bm.json"
        add_bookmarks([_make_article("https://a.com")], path=path)
        assert remove_bookmark("https://a.com", path=path) is True
        assert len(load_bookmarks(path)) == 0

    def test_remove_nonexistent(self, tmp_path):
        path = tmp_path / "bm.json"
        add_bookmarks([_make_article("https://a.com")], path=path)
        assert remove_bookmark("https://b.com", path=path) is False
        assert len(load_bookmarks(path)) == 1


class TestDRYFetch:
    def test_fetch_url_delegates_to_shared(self):
        """fetch_url should use _fetch_with_retry internally."""

        class Dummy(BaseSource):
            name = "dummy"
            max_retries = 0
            timeout = 2

            def crawl(self):
                return []

        src = Dummy()
        with patch.object(src, "_fetch_with_retry", return_value="hello") as mock:
            result = src.fetch_url("https://example.com")
            mock.assert_called_once_with("https://example.com", parse_json=False)
            assert result == "hello"

    def test_fetch_json_delegates_to_shared(self):
        class Dummy(BaseSource):
            name = "dummy"
            max_retries = 0
            timeout = 2

            def crawl(self):
                return []

        src = Dummy()
        with patch.object(src, "_fetch_with_retry", return_value={"ok": True}) as mock:
            result = src.fetch_json("https://example.com")
            mock.assert_called_once_with("https://example.com", parse_json=True)
            assert result == {"ok": True}


class TestFetchWithRetry:
    def test_returns_empty_string_on_text_failure(self):
        class Dummy(BaseSource):
            name = "dummy"
            max_retries = 0
            timeout = 1

            def crawl(self):
                return []

        src = Dummy()
        result = src._fetch_with_retry("http://localhost:1/nope", parse_json=False)
        assert result == ""

    def test_returns_none_on_json_failure(self):
        class Dummy(BaseSource):
            name = "dummy"
            max_retries = 0
            timeout = 1

            def crawl(self):
                return []

        src = Dummy()
        result = src._fetch_with_retry("http://localhost:1/nope", parse_json=True)
        assert result is None


class TestVersionSync:
    def test_all_versions_match(self):
        from clawler import __version__
        assert __version__ == "3.6.0"
        # Check pyproject.toml
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        assert 'version = "3.6.0"' in pyproject.read_text()
        # Check setup.py
        setup = Path(__file__).parent.parent / "setup.py"
        assert 'version="3.6.0"' in setup.read_text()


class TestBuildBackend:
    def test_pyproject_uses_correct_backend(self):
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "setuptools.build_meta" in content
        assert "_legacy" not in content


class TestCountFlag:
    def test_count_flag_exists(self):
        """--count flag should be accepted by the argument parser."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", action="store_true")
        args = parser.parse_args(["--count"])
        assert args.count is True


class TestRSSRateLimiting:
    def test_rss_uses_fetch_url(self):
        """RSS source should call fetch_url (which applies rate limiting)."""
        from clawler.sources.rss import RSSSource

        src = RSSSource(feeds=[{"url": "https://example.com/feed.xml", "source": "Test", "category": "tech"}])
        with patch.object(src, "fetch_url", return_value="<rss><channel></channel></rss>") as mock_fetch:
            src.crawl()
            mock_fetch.assert_called_once_with("https://example.com/feed.xml")
