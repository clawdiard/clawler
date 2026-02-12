"""Base source class."""
from abc import ABC, abstractmethod
from typing import List
from clawler.models import Article
import requests
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Clawler/1.0 (News Aggregator; +https://github.com/clawdiard/clawler)"
}


class BaseSource(ABC):
    """Abstract base for all news sources."""

    name: str = "unknown"
    timeout: int = 15

    def fetch_url(self, url: str) -> str:
        """Fetch URL content with error handling."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning(f"[{self.name}] Failed to fetch {url}: {e}")
            return ""

    @abstractmethod
    def crawl(self) -> List[Article]:
        """Crawl the source and return articles."""
        ...
