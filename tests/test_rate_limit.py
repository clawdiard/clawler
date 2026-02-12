"""Tests for per-domain rate limiting in BaseSource."""
import time
from clawler.sources.base import _domain_last_request, _RATE_LIMIT_SECONDS, BaseSource


class DummySource(BaseSource):
    name = "dummy"
    def crawl(self):
        return []


def test_rate_limit_records_domain():
    _domain_last_request.clear()
    src = DummySource()
    src._rate_limit("https://example.com/page1")
    assert "example.com" in _domain_last_request


def test_rate_limit_delays_same_domain():
    _domain_last_request.clear()
    src = DummySource()
    src._rate_limit("https://example.com/a")
    t0 = time.time()
    src._rate_limit("https://example.com/b")
    elapsed = time.time() - t0
    # Should have waited ~0.5s (or close to it)
    assert elapsed >= _RATE_LIMIT_SECONDS * 0.8


def test_rate_limit_no_delay_different_domain():
    _domain_last_request.clear()
    src = DummySource()
    src._rate_limit("https://example.com/a")
    t0 = time.time()
    src._rate_limit("https://other.com/b")
    elapsed = time.time() - t0
    assert elapsed < _RATE_LIMIT_SECONDS
