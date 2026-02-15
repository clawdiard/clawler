"""Substack source — curated newsletter feeds via RSS.

Substack exposes every publication as an RSS feed at <slug>.substack.com/feed.
This source tracks popular Substack newsletters across tech, business, science,
culture, and policy categories.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from xml.etree import ElementTree as ET

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Curated Substack newsletters with categories
SUBSTACK_FEEDS = [
    # Tech & AI
    {"slug": "astralcodexten", "source": "Astral Codex Ten", "category": "tech"},
    {"slug": "oneusefulthing", "source": "One Useful Thing", "category": "tech"},
    {"slug": "platformer", "source": "Platformer", "category": "tech"},
    {"slug": "thealgorithmicbridge", "source": "The Algorithmic Bridge", "category": "tech"},
    {"slug": "importai", "source": "Import AI", "category": "tech"},
    {"slug": "chinaai", "source": "ChinAI", "category": "tech"},
    {"slug": "thesequence", "source": "TheSequence", "category": "tech"},
    {"slug": "aisnakeoil", "source": "AI Snake Oil", "category": "tech"},
    {"slug": "garymarcus", "source": "Marcus on AI", "category": "tech"},
    {"slug": "lenny", "source": "Lenny's Newsletter", "category": "business"},
    # Business & Startups
    {"slug": "stratechery", "source": "Stratechery", "category": "business"},
    {"slug": "thegeneralist", "source": "The Generalist", "category": "business"},
    {"slug": "newsletter.pragmaticengineer", "source": "Pragmatic Engineer", "category": "tech"},
    {"slug": "blog.bytebytego", "source": "ByteByteGo", "category": "tech"},
    {"slug": "semianalysis", "source": "SemiAnalysis", "category": "tech"},
    # Science
    {"slug": "dynomight", "source": "Dynomight", "category": "science"},
    {"slug": "experimentalhistory", "source": "Experimental History", "category": "science"},
    # Culture & Policy
    {"slug": "mattstoller", "source": "BIG by Matt Stoller", "category": "business"},
    {"slug": "noahpinion", "source": "Noahpinion", "category": "business"},
    {"slug": "slowboring", "source": "Slow Boring", "category": "culture"},
    # Security & Privacy
    {"slug": "lcamtuf", "source": "lcamtuf's thing", "category": "security"},
    {"slug": "therecord", "source": "The Record", "category": "security"},
]


class SubstackSource(BaseSource):
    """Fetches articles from curated Substack newsletters via RSS."""

    name = "Substack"
    timeout = 12

    def __init__(self, feeds: Optional[List[dict]] = None, max_per_feed: int = 5):
        self.feeds = feeds or SUBSTACK_FEEDS
        self.max_per_feed = max_per_feed

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        """Parse a single Substack RSS feed."""
        slug = feed_info["slug"]
        source_name = feed_info.get("source", slug)
        category = feed_info.get("category", "general")
        url = f"https://{slug}.substack.com/feed"

        text = self.fetch_url(url)
        if not text:
            return []

        articles: List[Article] = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            logger.warning(f"[Substack] XML parse error for {slug}: {e}")
            return []

        ns = {"dc": "http://purl.org/dc/elements/1.1/",
              "content": "http://purl.org/rss/1.0/modules/content/"}

        for item in root.findall(".//item")[:self.max_per_feed]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue

            description = (item.findtext("description") or "").strip()
            # Strip HTML tags from description
            import re
            clean_desc = re.sub(r"<[^>]+>", "", description)[:300].strip()

            author = (item.findtext("dc:creator", namespaces=ns)
                      or item.findtext("author") or "").strip()

            pub_date = item.findtext("pubDate")
            timestamp = None
            if pub_date:
                try:
                    from email.utils import parsedate_to_datetime
                    timestamp = parsedate_to_datetime(pub_date)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            summary = clean_desc
            if author:
                summary = f"by {author} — {summary}"

            articles.append(Article(
                title=title,
                url=link,
                source=f"Substack ({source_name})",
                summary=summary[:300],
                timestamp=timestamp,
                category=category,
                author=author,
            ))

        return articles

    def crawl(self) -> List[Article]:
        """Crawl all configured Substack feeds."""
        all_articles: List[Article] = []
        for feed_info in self.feeds:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[Substack] Error crawling {feed_info.get('slug', '?')}: {e}")

        logger.info(f"[Substack] Fetched {len(all_articles)} articles from {len(self.feeds)} newsletters")
        return all_articles
