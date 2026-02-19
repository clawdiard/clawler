"""NPR source — fetches articles from NPR's public RSS feeds.

Enhanced: 18 section feeds, keyword-based category detection, quality scoring,
author reputation, cross-section deduplication, filters.
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

# NPR section RSS feeds — expanded from 10 to 18
NPR_FEEDS = [
    {"url": "https://feeds.npr.org/1001/rss.xml", "section": "News", "category": "world", "prominence": 0.50},
    {"url": "https://feeds.npr.org/1014/rss.xml", "section": "Politics", "category": "world", "prominence": 0.48},
    {"url": "https://feeds.npr.org/1007/rss.xml", "section": "Science", "category": "science", "prominence": 0.45},
    {"url": "https://feeds.npr.org/1019/rss.xml", "section": "Technology", "category": "tech", "prominence": 0.44},
    {"url": "https://feeds.npr.org/1008/rss.xml", "section": "Culture", "category": "culture", "prominence": 0.40},
    {"url": "https://feeds.npr.org/1128/rss.xml", "section": "Health", "category": "health", "prominence": 0.45},
    {"url": "https://feeds.npr.org/1006/rss.xml", "section": "Business", "category": "business", "prominence": 0.42},
    {"url": "https://feeds.npr.org/1057/rss.xml", "section": "Economy", "category": "business", "prominence": 0.42},
    {"url": "https://feeds.npr.org/1032/rss.xml", "section": "Education", "category": "education", "prominence": 0.40},
    {"url": "https://feeds.npr.org/1052/rss.xml", "section": "Books", "category": "culture", "prominence": 0.38},
    {"url": "https://feeds.npr.org/1039/rss.xml", "section": "Music", "category": "culture", "prominence": 0.38},
    {"url": "https://feeds.npr.org/1045/rss.xml", "section": "Movies", "category": "culture", "prominence": 0.37},
    {"url": "https://feeds.npr.org/1024/rss.xml", "section": "Environment", "category": "environment", "prominence": 0.44},
    {"url": "https://feeds.npr.org/1003/rss.xml", "section": "National", "category": "world", "prominence": 0.48},
    {"url": "https://feeds.npr.org/1004/rss.xml", "section": "World", "category": "world", "prominence": 0.50},
    {"url": "https://feeds.npr.org/1017/rss.xml", "section": "Race", "category": "culture", "prominence": 0.40},
    {"url": "https://feeds.npr.org/1149/rss.xml", "section": "Climate", "category": "environment", "prominence": 0.44},
    {"url": "https://feeds.npr.org/1053/rss.xml", "section": "Food", "category": "culture", "prominence": 0.36},
]

# Two-tier keyword category detection — specific categories first
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "chatgpt", "openai", "llm", "large language model", "generative ai", "gpt",
        "ai model", "ai tool", "copilot", "claude", "gemini", "transformer",
    ],
    "security": [
        "cybersecurity", "hack", "breach", "ransomware", "malware", "phishing",
        "vulnerability", "zero-day", "encryption", "privacy", "surveillance",
        "data breach", "cyber attack", "espionage",
    ],
    "crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "blockchain", "defi", "nft",
        "crypto", "web3", "stablecoin", "token", "mining",
    ],
    "health": [
        "vaccine", "pandemic", "virus", "disease", "mental health", "drug",
        "fda", "clinical trial", "cancer", "therapy", "diagnosis", "hospital",
        "medical", "public health", "cdc", "who",
    ],
    "science": [
        "nasa", "space", "climate", "physics", "biology", "chemistry",
        "genome", "fossil", "earthquake", "species", "ocean", "telescope",
        "quantum", "mars", "asteroid", "evolution",
    ],
    "business": [
        "stock", "market", "economy", "inflation", "federal reserve", "gdp",
        "earnings", "ipo", "merger", "acquisition", "layoff", "startup",
        "venture capital", "recession", "trade",
    ],
    "education": [
        "school", "university", "student", "teacher", "college", "campus",
        "tuition", "graduation", "curriculum", "academic",
    ],
    "environment": [
        "climate change", "global warming", "emissions", "renewable",
        "fossil fuel", "deforestation", "biodiversity", "pollution",
        "sustainability", "carbon", "wildfire", "drought", "flooding",
    ],
    "culture": [
        "music", "film", "movie", "book", "album", "concert", "festival",
        "art", "museum", "theater", "oscars", "grammy", "emmy",
    ],
    "gaming": [
        "video game", "gaming", "xbox", "playstation", "nintendo",
        "esports", "steam", "twitch",
    ],
    "design": [
        "design", "ux", "user experience", "interface", "typography",
        "accessibility", "figma",
    ],
}

# Prominent NPR journalists — get quality boost
PROMINENT_AUTHORS = {
    "mary louise kelly", "ari shapiro", "ailsa chang", "leila fadel",
    "juana summers", "scott detrow", "ayesha rascoe", "steve inskeep",
    "a martinez", "sacha pfeiffer", "rachel martin", "david folkenflik",
    "nina totenberg", "shankar vedantam", "terry gross", "ina jaffe",
    "audie cornish", "scott simon", "lulu garcia-navarro",
}

import math


def _detect_category(title: str, summary: str) -> Optional[str]:
    """Two-tier keyword category detection — specific > generic."""
    text = f"{title} {summary}".lower()
    best_cat = None
    best_hits = 0
    for cat, keywords in KEYWORD_CATEGORIES.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    return best_cat


def _compute_quality(position: int, total: int, section_prominence: float,
                     author: str, category: str) -> float:
    """Quality score 0–1 based on position, section prominence, author reputation."""
    # Position decay: first article gets full prominence, later ones decay
    if total > 1:
        position_factor = 1.0 - (position / (total * 1.5))
    else:
        position_factor = 1.0
    position_factor = max(position_factor, 0.3)

    score = section_prominence * position_factor

    # Author reputation boost
    if author and author.lower() in PROMINENT_AUTHORS:
        score = min(score + 0.12, 1.0)

    # Specific category boost (ai, security, environment get slight bump)
    if category in ("ai", "security", "environment", "crypto"):
        score = min(score + 0.05, 1.0)

    return round(score, 3)


def _format_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class NPRSource(BaseSource):
    """Crawl NPR section RSS feeds with quality scoring and smart categories.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles matching these categories.
    exclude_sections : list of str or None
        Sections to exclude.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "npr"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        limit: int = 15,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None
        self.global_limit = global_limit

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        """Parse a single NPR RSS feed into articles with quality scoring."""
        url = feed_info["url"]
        section = feed_info["section"]
        default_category = feed_info["category"]
        prominence = feed_info["prominence"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []
        entries = parsed.entries[: self.limit]
        total = len(entries)

        for i, entry in enumerate(entries):
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            # Dedup across sections
            if link in seen_urls:
                continue
            seen_urls.add(link)

            summary = entry.get("summary", "").strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    # Truncate at sentence boundary
                    cut = summary[:300].rfind(".")
                    if cut > 150:
                        summary = summary[: cut + 1]
                    else:
                        summary = summary[:297] + "..."

            # Parse publication date
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

            # Two-tier category: keyword detection → section default
            detected = _detect_category(title, summary or "")
            category = detected if detected else default_category

            # Quality score
            quality = _compute_quality(i, total, prominence, author, category)

            # Apply filters
            if quality < self.min_quality:
                continue
            if self.category_filter and category not in self.category_filter:
                continue

            # Build rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 {section}")
            if summary:
                parts.append(summary)
            rich_summary = " · ".join(parts[:2])
            if summary:
                rich_summary += f" — {summary}"

            # Provenance tags
            tags = [
                f"npr:section:{section.lower()}",
                f"npr:category:{category}",
            ]
            if author:
                author_tag = re.sub(r"[^a-z0-9]+", "-", author.lower()).strip("-")
                tags.append(f"npr:author:{author_tag}")
            if author and author.lower() in PROMINENT_AUTHORS:
                tags.append("npr:prominent-author")

            articles.append(Article(
                title=title,
                url=link,
                source=f"NPR ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = NPR_FEEDS

        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]
        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"].lower() not in self.exclude_sections]

        seen_urls: Set[str] = set()
        all_articles = []

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[NPR] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[NPR] Failed to parse {feed_info['section']}: {e}")

        # Sort by quality (best first)
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Apply global limit
        if self.global_limit and len(all_articles) > self.global_limit:
            all_articles = all_articles[: self.global_limit]

        logger.info(f"[NPR] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
