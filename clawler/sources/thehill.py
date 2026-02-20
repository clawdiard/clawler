"""The Hill source — fetches articles from The Hill RSS feeds.

The Hill is a top US political news outlet covering Congress, the White House,
policy, campaigns, and opinion. Free RSS feeds, no API key required.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

THEHILL_FEEDS = [
    {"url": "https://thehill.com/feed/", "section": "Top Stories", "category": "politics"},
    {"url": "https://thehill.com/homenews/feed/", "section": "News", "category": "politics"},
    {"url": "https://thehill.com/policy/feed/", "section": "Policy", "category": "politics"},
    {"url": "https://thehill.com/regulation/feed/", "section": "Regulation", "category": "politics"},
    {"url": "https://thehill.com/business/feed/", "section": "Business", "category": "business"},
    {"url": "https://thehill.com/policy/technology/feed/", "section": "Technology", "category": "tech"},
    {"url": "https://thehill.com/policy/healthcare/feed/", "section": "Healthcare", "category": "health"},
    {"url": "https://thehill.com/policy/energy-environment/feed/", "section": "Energy & Environment", "category": "science"},
    {"url": "https://thehill.com/policy/defense/feed/", "section": "Defense", "category": "world"},
    {"url": "https://thehill.com/policy/national-security/feed/", "section": "National Security", "category": "security"},
    {"url": "https://thehill.com/opinion/feed/", "section": "Opinion", "category": "politics"},
    {"url": "https://thehill.com/latino/feed/", "section": "Latino", "category": "politics"},
]

# Keywords for category refinement
_CATEGORY_KEYWORDS = {
    "security": {"cybersecurity", "hacking", "breach", "surveillance", "encryption",
                 "espionage", "intelligence agency", "homeland security", "terrorism"},
    "tech": {"artificial intelligence", "tech company", "software", "algorithm", "big data",
             "social media", "tiktok", "google", "apple", "meta", "microsoft"},
    "world": {"nato", "ukraine", "china", "europe", "foreign", "diplomacy", "sanctions",
              "russia", "middle east", "iran", "israel"},
    "business": {"economy", "inflation", "jobs", "trade", "tariff", "fed ", "stock",
                 "wall street", "gdp", "recession"},
}

# Notable Hill authors for quality boost
_PROMINENT_AUTHORS = frozenset({
    "alexander bolton", "mike lillis", "jordain carney", "brett samuels",
    "morgan chalfant", "emily brooks", "hanna trudo", "mychael schnell",
    "aris folley", "rafael bernal", "karl evers-hillstrom",
})


class TheHillSource(BaseSource):
    """Crawl The Hill RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    """

    name = "thehill"

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

            # Keyword-based category refinement
            text_lower = f"{title} {summary}".lower()
            refined_category = category
            for cat, keywords in _CATEGORY_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    refined_category = cat
                    break

            # Quality scoring
            quality = 0.74  # solid political journalism baseline
            if author and author.lower() in _PROMINENT_AUTHORS:
                quality += 0.06
            if section == "Opinion":
                quality -= 0.05  # opinion slightly lower than news

            tags = [f"thehill:{section.lower().replace(' & ', '_').replace(' ', '_')}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"The Hill ({section})",
                summary=summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=round(quality, 2),
            ))

        return articles

    def crawl(self) -> List[Article]:
        articles = []
        for feed_info in THEHILL_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles.extend(self._parse_feed(feed_info))
            except Exception as exc:
                logger.warning("The Hill %s failed: %s", feed_info["section"], exc)
        return articles
