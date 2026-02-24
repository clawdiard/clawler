"""Politico source — fetches articles from Politico RSS feeds.

Politico is a leading political journalism outlet covering US and global
politics, policy, and power dynamics. Free RSS feeds, no API key required.

Enhanced features:
- 12 section feeds (was 8): added White House, Foreign Policy, Trade, Justice
- Quality scoring (0–1) based on section prominence × position decay + author boost
- Two-tier keyword category detection (10 specific categories)
- Prominent journalist detection (12+ Politico writers) with reputation boost
- Cross-feed URL deduplication
- Filters: min_quality, category_filter, global_limit
- Rich summaries with ✍️ author · 🏛️ section · description
- Provenance tags: politico:section, politico:category, politico:author, politico:prominent-author
"""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Section feeds with prominence weights (higher = more important section)
POLITICO_FEEDS = [
    {"url": "https://rss.politico.com/politics-news.xml", "section": "Politics", "category": "politics", "prominence": 1.0},
    {"url": "https://rss.politico.com/congress.xml", "section": "Congress", "category": "politics", "prominence": 0.95},
    {"url": "https://rss.politico.com/whitehouse.xml", "section": "White House", "category": "politics", "prominence": 0.95},
    {"url": "https://rss.politico.com/economy.xml", "section": "Economy", "category": "business", "prominence": 0.88},
    {"url": "https://rss.politico.com/healthcare.xml", "section": "Healthcare", "category": "health", "prominence": 0.82},
    {"url": "https://rss.politico.com/defense.xml", "section": "Defense", "category": "world", "prominence": 0.85},
    {"url": "https://rss.politico.com/energy.xml", "section": "Energy", "category": "science", "prominence": 0.78},
    {"url": "https://rss.politico.com/technology.xml", "section": "Technology", "category": "tech", "prominence": 0.84},
    {"url": "https://rss.politico.com/education.xml", "section": "Education", "category": "education", "prominence": 0.72},
    {"url": "https://rss.politico.com/foreignpolicy.xml", "section": "Foreign Policy", "category": "world", "prominence": 0.90},
    {"url": "https://rss.politico.com/trade.xml", "section": "Trade", "category": "business", "prominence": 0.80},
    {"url": "https://rss.politico.com/justice.xml", "section": "Justice", "category": "politics", "prominence": 0.86},
]

# Prominent Politico journalists — get a quality boost
_PROMINENT_AUTHORS: Set[str] = {
    "jonathan martin", "ryan lizza", "rachael bade", "eugene daniels",
    "sam stein", "josh gerstein", "adam cancryn", "ben white",
    "nancy cook", "tina sfondeles", "alex ward", "natasha bertrand",
    "meridith mcgraw", "lara seligman",
}

# Keyword → category mapping (first match wins; more specific first)
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "security": ["cybersecurity", "hack", "breach", "nsa", "surveillance", "encryption", "cyber"],
    "tech": ["ai ", "artificial intelligence", "tech giant", "software", "algorithm", "data privacy", "silicon valley"],
    "world": ["nato", "ukraine", "china", "europe", "foreign", "diplomacy", "sanctions", "middle east", "russia"],
    "business": ["wall street", "trade war", "tariff", "gdp", "inflation", "tax", "budget", "deficit"],
    "health": ["pandemic", "vaccine", "fda", "medicare", "medicaid", "obamacare", "health care"],
    "science": ["climate", "epa", "renewable", "emissions", "nuclear", "energy"],
    "investigative": ["investigation", "probe", "subpoena", "indictment", "scandal", "whistleblower"],
    "politics": ["election", "campaign", "ballot", "primary", "caucus", "senate", "house"],
}


def _position_decay(index: int, total: int) -> float:
    """Position-based decay: top articles score higher. Returns 0.6–1.0."""
    if total <= 1:
        return 1.0
    return 1.0 - 0.4 * (index / (total - 1))


def _compute_quality(prominence: float, position: int, total: int,
                     is_prominent_author: bool) -> float:
    """Compute quality score from section prominence × position + author boost."""
    base = prominence * _position_decay(position, total)
    author_boost = 0.06 if is_prominent_author else 0.0
    return min(1.0, round(base * 0.78 + 0.22 + author_boost, 4))


class PoliticoSource(BaseSource):
    """Crawl Politico RSS feeds with quality scoring and category detection.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    min_quality : float
        Minimum quality score to include. Default 0.0.
    category_filter : str or None
        Only include articles matching this category.
    global_limit : int or None
        Max total articles across all feeds.
    """

    name = "politico"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 15,
                 min_quality: float = 0.0, category_filter: Optional[str] = None,
                 global_limit: Optional[int] = None):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = category_filter.lower() if category_filter else None
        self.global_limit = global_limit

    def _refine_category(self, base_category: str, title: str, summary: str) -> str:
        """Keyword-based category refinement."""
        text_lower = f"{title} {summary}".lower()
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return cat
        return base_category

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        category = feed_info["category"]
        prominence = feed_info["prominence"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        entries = parsed.entries[:self.limit]
        total = len(entries)
        articles = []

        for idx, entry in enumerate(entries):
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            # Cross-feed dedup
            normalized = re.sub(r"(https?://)?(www\.)?", "", link).rstrip("/")
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

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
            is_prominent = author.lower().strip() in _PROMINENT_AUTHORS if author else False

            refined_category = self._refine_category(category, title, summary)
            quality = _compute_quality(prominence, idx, total, is_prominent)

            if quality < self.min_quality:
                continue
            if self.category_filter and refined_category != self.category_filter:
                continue

            # Rich summary
            parts = []
            if author:
                prefix = "✍️⭐" if is_prominent else "✍️"
                parts.append(f"{prefix} {author}")
            parts.append(f"🏛️ {section}")
            if summary:
                parts.append(summary)
            rich_summary = " · ".join(parts)

            tags = [f"politico:{section.lower().replace(' ', '_')}",
                    f"politico:{refined_category}"]
            if author:
                tags.append(f"politico:author:{author.lower().strip()}")
            if is_prominent:
                tags.append("politico:prominent-author")

            articles.append(Article(
                title=title,
                url=link,
                source=f"Politico ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=refined_category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        for feed_info in POLITICO_FEEDS:
            if self.sections and feed_info["section"].lower() not in self.sections:
                continue
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[Politico] {feed_info['section']}: {len(articles)} articles")
            except Exception as exc:
                logger.warning("Politico %s failed: %s", feed_info["section"], exc)

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[Politico] Total: {len(all_articles)} articles from {len(POLITICO_FEEDS)} sections")
        return all_articles
