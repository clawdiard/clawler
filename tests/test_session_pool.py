"""Tests for connection pooling via shared requests.Session."""
import threading
from clawler.sources.base import _get_session, _session_lock


class TestSessionPool:
    def test_returns_session(self):
        session = _get_session()
        assert session is not None

    def test_singleton(self):
        s1 = _get_session()
        s2 = _get_session()
        assert s1 is s2

    def test_has_adapters(self):
        session = _get_session()
        adapter = session.get_adapter("https://example.com")
        assert adapter is not None
        assert adapter._pool_connections == 20
        assert adapter._pool_maxsize == 20

    def test_thread_safe(self):
        """Multiple threads should all get the same session."""
        results = []

        def grab():
            results.append(id(_get_session()))

        threads = [threading.Thread(target=grab) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(set(results)) == 1
