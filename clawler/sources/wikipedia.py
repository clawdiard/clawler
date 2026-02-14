"""Wikipedia Current Events source — curated daily news from Wikipedia editors.

Parses the Wikipedia Current Events portal, which provides a human-curated
summary of notable world events updated daily. No API key required.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

PORTAL_URL = "https://en.wikipedia.org/wiki/Portal:Current_events"


class WikipediaCurrentEventsSource(BaseSource):
    """Crawl today's curated events from Wikipedia's Current Events portal."""

    name = "wikipedia"

    def crawl(self) -> List[Article]:
        from bs4 import BeautifulSoup

        html = self.fetch_url(PORTAL_URL)
        if not html:
            logger.warning("[Wikipedia] Failed to fetch Current Events portal")
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles: List[Article] = []
        seen_urls: set = set()

        # The portal organizes events under date headings and category sub-headings.
        # Each event is an <li> with links to external news sources and Wikipedia articles.
        # We look for the most recent day's content block.
        content_div = soup.find("div", {"class": "current-events-content"})
        if not content_div:
            # Fallback: look for any vevent or description containers
            content_div = soup.find("div", {"role": "region"}) or soup

        # Find category headings and their items
        current_category = "world"
        for element in content_div.find_all(["b", "li", "p"]):
            # Detect category labels (bold text like "Armed conflicts", "Science", etc.)
            if element.name in ("b", "p"):
                cat_text = element.get_text(strip=True).lower()
                current_category = _map_category(cat_text)
                continue

            if element.name != "li":
                continue

            # Extract the event text and any linked URLs
            text = element.get_text(" ", strip=True)
            if not text or len(text) < 20:
                continue

            # Find external links (non-Wikipedia) — these are the news source links
            links = element.find_all("a", href=True)
            ext_url = None
            wiki_url = None
            for link in links:
                href = link["href"]
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/wiki/"):
                    href = "https://en.wikipedia.org" + href

                if "wikipedia.org" not in href and href.startswith("http"):
                    ext_url = ext_url or href
                elif "wikipedia.org" in href and "/wiki/" in href:
                    wiki_url = wiki_url or href

            # Use the best available URL
            url = ext_url or wiki_url
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            # Clean up the title: take the first sentence or first ~120 chars
            title = text[:150].split(". ")[0].strip()
            if not title:
                continue

            articles.append(Article(
                title=title,
                url=url,
                source="Wikipedia Current Events",
                summary=text[:300] if len(text) > 150 else "",
                timestamp=datetime.now(tz=timezone.utc),
                category=current_category,
                quality_score=0.80,  # curated by Wikipedia editors = high quality
                tags=["wikipedia", "curated"],
            ))

        logger.info(f"[Wikipedia] Collected {len(articles)} current events")
        return articles


def _map_category(text: str) -> str:
    """Map Wikipedia Current Events section headings to Clawler categories."""
    if any(kw in text for kw in ("armed", "conflict", "attack", "war", "militar")):
        return "world"
    if any(kw in text for kw in ("politic", "election", "govern", "law", "legislat", "diplomacy")):
        return "world"
    if any(kw in text for kw in ("disaster", "environment", "climate", "weather")):
        return "science"
    if any(kw in text for kw in ("science", "technology", "space", "health", "medicine")):
        return "science"
    if any(kw in text for kw in ("business", "econom", "financ", "market", "trade")):
        return "business"
    if any(kw in text for kw in ("sport",)):
        return "culture"
    if any(kw in text for kw in ("art", "culture", "entertain", "film", "music", "death")):
        return "culture"
    return "world"
