"""Indie Hackers source — trending posts from indiehackers.com."""
import logging
from datetime import datetime, timezone
from typing import List
from bs4 import BeautifulSoup
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

INDIE_HACKERS_URL = "https://www.indiehackers.com/"


class IndieHackersSource(BaseSource):
    """Scrape trending posts from Indie Hackers front page."""

    name = "Indie Hackers"
    timeout = 15

    def crawl(self) -> List[Article]:
        html = self.fetch_url(INDIE_HACKERS_URL)
        if not html:
            return []

        articles: List[Article] = []
        soup = BeautifulSoup(html, "html.parser")

        # Try to find post links — IH uses various selectors; be resilient
        seen_urls = set()
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # IH post links look like /post/... or full URLs
            if "/post/" not in href:
                continue
            if href.startswith("/"):
                href = f"https://www.indiehackers.com{href}"
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            articles.append(Article(
                title=title,
                url=href,
                source=self.name,
                category="business",
                timestamp=datetime.now(tz=timezone.utc),
                summary="",
            ))

        logger.info(f"[{self.name}] Found {len(articles)} posts")
        return articles
