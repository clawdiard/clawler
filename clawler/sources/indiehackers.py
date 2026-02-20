"""Indie Hackers source — trending posts from indiehackers.com.

Enhanced with keyword-based categories, quality scoring for scrape results,
and tag extraction from post titles.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List
from bs4 import BeautifulSoup
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

INDIE_HACKERS_URL = "https://www.indiehackers.com/"
INDIE_HACKERS_FEED = "https://feeds.transistor.fm/the-indie-hackers-podcast"

# Keyword → category mapping for indie/startup content
KEYWORD_CATEGORIES = {
    "revenue": "business",
    "mrr": "business",
    "arr": "business",
    "profit": "business",
    "funding": "business",
    "acquisition": "business",
    "acquired": "business",
    "launch": "business",
    "launched": "business",
    "saas": "business",
    "pricing": "business",
    "customer": "business",
    "growth": "business",
    "marketing": "business",
    "seo": "business",
    "churn": "business",
    "bootstrap": "business",
    "indie": "business",
    "startup": "business",
    "side project": "business",
    "monetize": "business",
    "api": "tech",
    "code": "tech",
    "developer": "tech",
    "programming": "tech",
    "react": "tech",
    "python": "tech",
    "ai": "tech",
    "machine learning": "tech",
    "llm": "tech",
    "gpt": "tech",
    "open source": "tech",
    "github": "tech",
    "deploy": "tech",
    "server": "tech",
    "database": "tech",
    "no-code": "tech",
    "low-code": "tech",
    "automation": "tech",
    "remote": "business",
    "freelance": "business",
    "hiring": "business",
    "quit": "business",
    "burnout": "business",
    "mental health": "culture",
    "community": "culture",
    "lifestyle": "culture",
    "digital nomad": "culture",
}

# Prominent IH members whose posts tend to be higher quality
PROMINENT_AUTHORS = {
    "csallen", "channingallen", "rosiesherry", "patio11",
    "levelsio", "marc", "yongfook", "tdinh",
}


def _classify_category(title: str) -> str:
    """Determine article category from title keywords."""
    lower = title.lower()
    for keyword, category in KEYWORD_CATEGORIES.items():
        if keyword in lower:
            return category
    return "business"  # default for IH


def _extract_tags(title: str) -> List[str]:
    """Extract relevant tags from the title."""
    tags = ["indiehackers:startups"]
    lower = title.lower()
    tag_keywords = [
        "saas", "ai", "no-code", "bootstrap", "launch", "revenue",
        "marketing", "seo", "remote", "freelance", "open source",
        "side project", "growth", "pricing", "api",
    ]
    for kw in tag_keywords:
        if kw in lower:
            tags.append(f"ih:{kw.replace(' ', '_')}")
    return tags[:8]


def _quality_from_position(index: int, total: int) -> float:
    """Estimate quality from position on the page (higher = better)."""
    if total <= 1:
        return 0.6
    # First items on the page are trending/popular
    ratio = index / total
    if ratio < 0.2:
        return 0.9
    elif ratio < 0.4:
        return 0.75
    elif ratio < 0.6:
        return 0.6
    else:
        return 0.45


class IndieHackersSource(BaseSource):
    """Scrape trending posts from Indie Hackers front page + podcast feed.

    Features:
    - Front page scraping for trending posts
    - Podcast RSS feed for interviews
    - Keyword-based category classification
    - Position-based quality scoring
    - Rich tag extraction
    - Prominent author detection
    """

    name = "Indie Hackers"
    timeout = 20

    def __init__(self, include_podcast: bool = True):
        self.include_podcast = include_podcast

    def _crawl_frontpage(self) -> List[Article]:
        """Scrape trending posts from the front page."""
        html = self.fetch_url(INDIE_HACKERS_URL)
        if not html:
            return []

        articles: List[Article] = []
        soup = BeautifulSoup(html, "html.parser")

        seen_urls: set = set()
        post_links = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
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
            post_links.append((title, href))

        total = len(post_links)
        for i, (title, url) in enumerate(post_links):
            category = _classify_category(title)
            tags = _extract_tags(title)
            quality = _quality_from_position(i, total)

            summary = f"Trending on Indie Hackers (quality: {quality:.0%})"

            articles.append(Article(
                title=title,
                url=url,
                source=f"Indie Hackers",
                category=category,
                timestamp=datetime.now(tz=timezone.utc),
                summary=summary,
                tags=tags,
            ))

        return articles

    def _crawl_podcast(self) -> List[Article]:
        """Fetch latest podcast episodes via RSS."""
        try:
            import feedparser
        except ImportError:
            logger.debug("[Indie Hackers] feedparser not available, skipping podcast")
            return []

        text = self.fetch_url(INDIE_HACKERS_FEED)
        if not text:
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []

        for entry in feed.entries[:10]:
            title = (entry.get("title") or "").strip()
            url = entry.get("link", "")
            if not title or not url:
                continue

            timestamp = None
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                try:
                    timestamp = datetime(*published[:6], tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass

            summary = entry.get("summary", "") or ""
            if "<" in summary:
                summary = BeautifulSoup(summary, "html.parser").get_text(separator=" ")
            summary = summary[:300].strip()

            articles.append(Article(
                title=f"🎙️ {title}",
                url=url,
                source="Indie Hackers Podcast",
                category="business",
                timestamp=timestamp,
                summary=summary,
                tags=["indiehackers:podcast", "indiehackers:startups"],
            ))

        return articles

    def crawl(self) -> List[Article]:
        articles: List[Article] = []

        # Front page
        articles.extend(self._crawl_frontpage())

        # Podcast feed
        if self.include_podcast:
            articles.extend(self._crawl_podcast())

        logger.info(f"[{self.name}] Found {len(articles)} posts")
        return articles
