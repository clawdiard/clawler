"""Base source class."""
from abc import ABC, abstractmethod
from typing import List
from clawler.models import Article
import requests
import logging
import time

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Clawler/1.1 (News Aggregator; +https://github.com/clawdiard/clawler)"
}


class BaseSource(ABC):
    """Abstract base for all news sources."""

    name: str = "unknown"
    timeout: int = 15
    max_retries: int = 2
    retry_backoff: float = 1.0

    def fetch_url(self, url: str) -> str:
        """Fetch URL content with retries and error handling."""
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=self.timeout)
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

    @abstractmethod
    def crawl(self) -> List[Article]:
        """Crawl the source and return articles."""
        ...
