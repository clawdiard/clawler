"""Vox source — explanatory journalism covering policy, science, culture, and tech.

Vox Media's flagship publication with strong editorial voice.
Free RSS feeds, no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

VOX_FEEDS = [
    {"url": "https://www.vox.com/rss/index.xml", "section": "Latest", "category": "world"},
    {"url": "https://www.vox.com/rss/technology/index.xml", "section": "Technology", "category": "tech"},
    {"url": "https://www.vox.com/rss/policy/index.xml", "section": "Policy", "category": "politics"},
    {"url": "https://www.vox.com/rss/science/index.xml", "section": "Science", "category": "science"},
    {"url": "https://www.vox.com/rss/culture/index.xml", "section": "Culture", "category": "culture"},
    {"url": "https://www.vox.com/rss/money/index.xml", "section": "Money", "category": "business"},
    {"url": "https://www.vox.com/rss/climate/index.xml", "section": "Climate", "category": "science"},
    {"url": "https://www.vox.com/rss/world-politics/index.xml", "section": "World", "category": "world"},
]

_CATEGORY_KEYWORDS = {
    "tech": {"ai", "artificial intelligence", "machine learning", "startup", "software", "app", "crypto", "blockchain"},
    "science": {"climate", "research", "study", "brain", "nasa", "space", "evolution", "pandemic"},
    "politics": {"congress", "senate", "election", "democrat", "republican", "supreme court", "legislation", "vote"},
    "business": {"economy", "market", "inflation", "gdp", "trade", "investment", "wall street"},
    "security": {"cybersecurity", "hack", "breach", "surveillance", "national security"},
}

_PROMINENT_AUTHORS = {
    "kelsey piper", "sigal samuel", "dylan matthews", "ian millhiser",
    "li zhou", "andrew prokop", "nicole narea", "sean illing",
    "marin cogan", "rachel m. cohen", "kenny torrella",
}


class VoxSource(BaseSource):
    """Crawl Vox RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section. Default 15.
    """

    name = "vox"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        category = feed_info["category"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for entry in parsed.entries[:self.limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            summary = entry.get("summary", entry.get("description", "")).strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            ts = None
            for date_field in ("published", "updated"):
                raw = entry.get(date_field)
                if raw:
                    try:
                        ts = dateparser.parse(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            author = entry.get("author", "")

            # Quality scoring
            quality = 0.75
            if author and author.lower() in _PROMINENT_AUTHORS:
                quality = 0.90
            text_lower = f"{title} {summary}".lower()
            if any(kw in text_lower for kw in ("exclusive", "investigation", "analysis", "deep dive")):
                quality = min(quality + 0.10, 1.0)

            # Refine category via keywords
            refined_category = category
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    refined_category = cat
                    break

            tags = [f"vox:{section.lower().replace(' ', '_')}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"Vox ({section})",
                summary=summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        articles = []
        for feed_info in VOX_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info))
            except Exception as exc:
                logger.warning("Vox %s failed: %s", feed_info["section"], exc)
        return articles
