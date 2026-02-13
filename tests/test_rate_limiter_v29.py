"""Tests for the improved rate limiter (v2.9.0 — lock-free sleep)."""
import time
import threading
from clawler.sources.base import _domain_last_request, _RATE_LIMIT_SECONDS, BaseSource


class DummySource(BaseSource):
    name = "dummy"
    def crawl(self):
        return []


def test_different_domains_not_blocked():
    """Requests to different domains should proceed without waiting."""
    _domain_last_request.clear()
    src = DummySource()
    src._rate_limit("https://slow.com/a")
    t0 = time.time()
    src._rate_limit("https://fast.com/b")
    elapsed = time.time() - t0
    assert elapsed < _RATE_LIMIT_SECONDS, "Different domains should not block each other"


def test_concurrent_different_domains():
    """Two threads hitting different domains should both complete quickly."""
    _domain_last_request.clear()
    src = DummySource()
    results = {}

    def fetch(domain, key):
        t0 = time.time()
        src._rate_limit(f"https://{domain}/page")
        results[key] = time.time() - t0

    t1 = threading.Thread(target=fetch, args=("alpha.com", "a"))
    t2 = threading.Thread(target=fetch, args=("beta.com", "b"))
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert results["a"] < _RATE_LIMIT_SECONDS
    assert results["b"] < _RATE_LIMIT_SECONDS
