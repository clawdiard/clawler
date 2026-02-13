"""Base source class."""
from abc import ABC, abstractmethod
from typing import List
from clawler.models import Article
import requests
import logging
import time
import threading

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Clawler/2.8 (News Aggregator; +https://github.com/clawdiard/clawler)"
}

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

    def fetch_url(self, url: str, **kwargs) -> str:
        """Fetch URL content with retries, rate limiting, and error handling."""
        self._rate_limit(url)
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.get(url, headers={**HEADERS, **kwargs.get("extra_headers", {})},
                                     timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                if attempt < self.max_retries:
                    wait = self.retry_backoff * (2 ** attempt)
                    logger.info(f"[{self.name}] Retry {attempt+1}/{self.max_retries} for {url} in {wait:.1f}s")
                    time.sleep(wait)
                else:
                    logger.warning(f"[{self.name}] Failed to fetch {url} after {self.max_retries+1} attempts: {e}")
        return ""

    def fetch_json(self, url: str, **kwargs):
        """Fetch URL and parse JSON, with retries and rate limiting. Returns None on failure."""
        self._rate_limit(url)
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.get(url, headers={**HEADERS, **kwargs.get("extra_headers", {})},
                                     timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < self.max_retries:
                    wait = self.retry_backoff * (2 ** attempt)
                    logger.info(f"[{self.name}] Retry {attempt+1}/{self.max_retries} for {url} in {wait:.1f}s")
                    time.sleep(wait)
                else:
                    logger.warning(f"[{self.name}] Failed to fetch {url} after {self.max_retries+1} attempts: {e}")
        return None

    @abstractmethod
    def crawl(self) -> List[Article]:
        """Crawl the source and return articles."""
        ...
