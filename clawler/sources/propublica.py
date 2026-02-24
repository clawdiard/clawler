"""ProPublica source — independent, nonprofit investigative journalism.

ProPublica is a Pulitzer Prize-winning newsroom producing investigative
journalism in the public interest. Covers government accountability,
criminal justice, healthcare, education, technology, and environment.

Enhanced features (v10.83.0):
- Quality scoring (0–1) based on section prominence + keyword specificity + position
- Multi-feed support with 5 RSS sources
- Two-tier keyword category detection (9 categories)
- Rich summaries with author/section metadata
- Provenance tags: propublica:section, propublica:category, propublica:author
- Filters: min_quality, category_filter, global_limit
- Cross-feed URL deduplication
"""
import logging
import re
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# ProPublica RSS feeds by section
PROPUBLICA_FEEDS = [
    {"url": "https://feeds.propublica.org/propublica/main", "section": "Top Stories", "category": "investigative"},
    {"url": "https://www.propublica.org/feeds/propublica/articles", "section": "Articles", "category": "investigative"},
    {"url": "https://www.propublica.org/feeds/propublica/investigations", "section": "Investigations", "category": "investigative"},
    {"url": "https://www.propublica.org/feeds/propublica/data", "section": "Data", "category": "tech"},
    {"url": "https://www.propublica.org/feeds/propublica/local", "section": "Local", "category": "government"},
]

# Section prominence scores
SECTION_PROMINENCE: Dict[str, float] = {
    "Top Stories": 0.60,
    "Investigations": 0.55,
    "Articles": 0.50,
    "Data": 0.45,
    "Local": 0.40,
}

CATEGORY_KEYWORDS = {
    "criminal_justice": [
        "police", "prison", "court", "judge", "sentencing", "incarceration",
        "bail", "criminal", "prosecutor", "detention", "parole", "probation",
    ],
    "healthcare": [
        "health", "hospital", "medicare", "medicaid", "insurance", "pharma",
        "drug", "patient", "doctor", "nursing", "mental health", "pandemic",
    ],
    "education": [
        "school", "university", "student", "teacher", "education", "college",
        "campus", "tuition", "charter", "superintendent",
    ],
    "environment": [
        "climate", "pollution", "epa", "environmental", "water", "toxic",
        "emissions", "wildfire", "chemical", "oil spill", "contamination",
    ],
    "tech": [
        "tech", "ai", "algorithm", "data", "privacy", "surveillance",
        "social media", "platform", "facial recognition", "tracking",
    ],
    "government": [
        "congress", "senate", "federal", "government", "white house",
        "election", "vote", "lobby", "regulation", "oversight", "inspector general",
    ],
    "finance": [
        "bank", "wall street", "sec", "fraud", "tax", "irs", "financial",
        "corporate", "predatory", "lending", "debt",
    ],
    "housing": [
        "housing", "eviction", "landlord", "rent", "homelessness", "zoning",
        "foreclosure", "affordable housing",
    ],
    "labor": [
        "worker", "union", "wage", "osha", "workplace", "labor",
        "gig economy", "employment",
    ],
}


def _categorize(title: str, summary: str) -> str:
    """Two-tier category detection with hit counting."""
    text = f"{title} {summary}".lower()
    best_cat = None
    best_hits = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = category
    if best_cat and best_hits >= 1:
        return best_cat
    return "investigative"


def _compute_quality(section: str, category: str, default_category: str,
                     position: int, author: str) -> float:
    """Quality score (0–1) based on section prominence + position + specificity."""
    base = SECTION_PROMINENCE.get(section, 0.45)
    # Position decay
    position_factor = 1.0 / (1.0 + 0.05 * position)
    score = base * position_factor
    # Boost for specific keyword-detected category
    if category != default_category:
        score = min(1.0, score + 0.08)
    # ProPublica bylined long-form gets a boost
    if author:
        score = min(1.0, score + 0.05)
    return round(min(1.0, score), 3)


class ProPublicaSource(BaseSource):
    """Crawl ProPublica's RSS feeds.

    Parameters
    ----------
    limit : int
        Max articles per feed. Default 20.
    categories : list of str or None
        Filter to specific categories. None = all.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "propublica"

    def __init__(
        self,
        limit: int = 20,
        categories: Optional[List[str]] = None,
        min_quality: float = 0.0,
        global_limit: Optional[int] = None,
    ):
        self.limit = limit
        self.categories = [c.lower() for c in categories] if categories else None
        self.min_quality = min_quality
        self.global_limit = global_limit

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        default_category = feed_info["category"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for position, entry in enumerate(parsed.entries[:self.limit]):
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue
            if link in seen_urls:
                continue
            seen_urls.add(link)

            summary = entry.get("summary", "").strip()
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
            category = _categorize(title, summary)

            if self.categories and category not in self.categories:
                continue

            # Quality scoring
            quality = _compute_quality(section, category, default_category, position, author)

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
                f"propublica:section:{section.lower().replace(' ', '_')}",
                f"propublica:category:{category}",
            ]
            if author:
                tags.append(f"propublica:author:{author.lower()}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"ProPublica ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        all_articles = []
        seen_urls: Set[str] = set()

        for feed_info in PROPUBLICA_FEEDS:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[ProPublica] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[ProPublica] Failed to parse {feed_info['section']}: {e}")

        # Apply quality filter
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if (a.quality_score or 0) >= self.min_quality]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Global limit
        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[ProPublica] Total: {len(all_articles)} articles")
        return all_articles
