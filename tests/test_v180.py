"""Tests for v1.8.0 features."""
from clawler.sources.base import BaseSource
from clawler.models import Article


class TestFetchJson:
    def test_fetch_json_returns_none_on_bad_url(self):
        class DummySource(BaseSource):
            name = "dummy"
            max_retries = 0
            timeout = 2
            def crawl(self):
                return []
        src = DummySource()
        result = src.fetch_json("http://localhost:1/nope")
        assert result is None

    def test_fetch_url_returns_empty_on_bad_url(self):
        class DummySource(BaseSource):
            name = "dummy"
            max_retries = 0
            timeout = 2
            def crawl(self):
                return []
        src = DummySource()
        result = src.fetch_url("http://localhost:1/nope")
        assert result == ""
