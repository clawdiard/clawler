"""Base source class."""
from abc import ABC, abstractmethod
from typing import List
from clawler.models import Article
import random
import requests
import logging
import time
import threading

logger = logging.getLogger(__name__)

def _build_headers():
    from clawler import __version__
    return {
        "User-Agent": f"Clawler/{__version__} (News Aggregator; +https://github.com/clawdiard/clawler)"
    }

# Lazy-init to avoid circular imports; kept as module-level for back-compat
class _LazyHeaders(dict):
    _loaded = False
    def _ensure(self):
        if not self._loaded:
            self.update(_build_headers())
            self._loaded = True
    def __getitem__(self, key):
        self._ensure()
        return super().__getitem__(key)
    def __iter__(self):
        self._ensure()
        return super().__iter__()
    def __len__(self):
        self._ensure()
        return super().__len__()
    def __repr__(self):
        self._ensure()
        return super().__repr__()
    def items(self):
        self._ensure()
        return super().items()
    def keys(self):
        self._ensure()
        return super().keys()
    def values(self):
        self._ensure()
        return super().values()
    def get(self, key, default=None):
        self._ensure()
        return super().get(key, default)
    def __contains__(self, key):
        self._ensure()
        return super().__contains__(key)
    def copy(self):
        self._ensure()
        return dict(self)
    def __or__(self, other):
        self._ensure()
        return dict.__or__(dict(self), other)
    def __ror__(self, other):
        self._ensure()
        return dict.__or__(other, dict(self))

HEADERS = _LazyHeaders()

# Shared session for connection pooling (TCP keep-alive, connection reuse)
_session: requests.Session | None = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    """Return a shared requests.Session for connection pooling."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                s = requests.Session()
                # Increase pool size for parallel crawling
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=20,
                    pool_maxsize=20,
                    max_retries=0,  # We handle retries ourselves
                )
                s.mount("https://", adapter)
                s.mount("http://", adapter)
                _session = s
    return _session


# Per-domain rate limiting — minimum seconds between requests to the same domain
_domain_last_request: dict = {}  # domain -> last request timestamp
_rate_limit_lock = threading.Lock()
_RATE_LIMIT_SECONDS = 0.5


class BaseSource(ABC):
    """Abstract base for all news sources."""

    name: str = "unknown"
    timeout: int = 15
    max_retries: int = 2
    retry_backoff: float = 1.0
    retry_jitter: float = 0.5  # random jitter factor (0-1) added to backoff
    config: dict  # per-source configuration (populated by caller or defaults to {})

    def __init__(self, **kwargs):
        self.config = kwargs

    @staticmethod
    def _rate_limit(url: str):
        """Enforce per-domain rate limiting (thread-safe).

        Calculates wait time under the lock but sleeps outside it so other
        domains are not blocked while one domain is being throttled.
        """
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        wait_time = 0.0
        with _rate_limit_lock:
            if domain in _domain_last_request:
                elapsed = time.time() - _domain_last_request[domain]
                if elapsed < _RATE_LIMIT_SECONDS:
                    wait_time = _RATE_LIMIT_SECONDS - elapsed
            # Reserve the slot immediately so concurrent requests to the same
            # domain queue up properly.
            _domain_last_request[domain] = time.time() + wait_time
        if wait_time > 0:
            time.sleep(wait_time)
        with _rate_limit_lock:
            _domain_last_request[domain] = time.time()

    def _fetch_with_retry(self, url: str, parse_json: bool = False, **kwargs):
        """Shared fetch logic with retries, rate limiting, and error handling.

        Returns response text (str) or parsed JSON (dict/list) on success.
        Returns the appropriate empty value ("" for text, None for JSON) on failure.
        """
        self._rate_limit(url)
        empty = None if parse_json else ""
        for attempt in range(self.max_retries + 1):
            try:
                session = _get_session()
                resp = session.get(url, headers={**HEADERS, **kwargs.get("extra_headers", {})},
                                     timeout=self.timeout)
                resp.raise_for_status()
                return resp.json() if parse_json else resp.text
            except requests.RequestException as e:
                if attempt < self.max_retries:
                    base_wait = self.retry_backoff * (2 ** attempt)
                    wait = base_wait + random.uniform(0, base_wait * self.retry_jitter)
                    logger.info(f"[{self.name}] Retry {attempt+1}/{self.max_retries} for {url} in {wait:.1f}s")
                    time.sleep(wait)
                else:
                    logger.warning(f"[{self.name}] Failed to fetch {url} after {self.max_retries+1} attempts: {e}")
        return empty

    def fetch_url(self, url: str, **kwargs) -> str:
        """Fetch URL content with retries, rate limiting, and error handling."""
        return self._fetch_with_retry(url, parse_json=False, **kwargs)

    def fetch_json(self, url: str, **kwargs):
        """Fetch URL and parse JSON, with retries and rate limiting. Returns None on failure."""
        return self._fetch_with_retry(url, parse_json=True, **kwargs)

    @abstractmethod
    def crawl(self) -> List[Article]:
        """Crawl the source and return articles."""
        ...
