"""AP News source — fetches articles from the Associated Press RSS feeds.

AP News is one of the most widely-trusted wire services globally.
Covers: top news, world, US, politics, business, technology, science, health, sports, entertainment.
All feeds are freely available RSS via RSSHub — no API key required.

Enhanced features:
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on section prominence + position decay + keyword specificity
- Prominent journalist detection with reputation boost
- Cross-section URL deduplication
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with ✍️ author · 📰 section · description
- Provenance tags: apnews:section, apnews:category, apnews:author, apnews:prominent-author
"""
import logging
import math
import re
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

AP_FEEDS = [
    {"url": "https://rsshub.app/apnews/topics/apf-topnews", "section": "Top News", "category": "world"},
    {"url": "https://rsshub.app/apnews/topics/apf-WorldNews", "section": "World", "category": "world"},
    {"url": "https://rsshub.app/apnews/topics/apf-usnews", "section": "US News", "category": "world"},
    {"url": "https://rsshub.app/apnews/topics/apf-politics", "section": "Politics", "category": "world"},
    {"url": "https://rsshub.app/apnews/topics/apf-business", "section": "Business", "category": "business"},
    {"url": "https://rsshub.app/apnews/topics/apf-technology", "section": "Technology", "category": "tech"},
    {"url": "https://rsshub.app/apnews/topics/apf-science", "section": "Science", "category": "science"},
    {"url": "https://rsshub.app/apnews/topics/apf-Health", "section": "Health", "category": "health"},
    {"url": "https://rsshub.app/apnews/topics/apf-sports", "section": "Sports", "category": "sports"},
    {"url": "https://rsshub.app/apnews/topics/apf-entertainment", "section": "Entertainment", "category": "culture"},
    {"url": "https://rsshub.app/apnews/topics/apf-oddities", "section": "Oddities", "category": "culture"},
    {"url": "https://rsshub.app/apnews/topics/apf-lifestyle", "section": "Lifestyle", "category": "culture"},
]

# Section prominence scores (AP editorial weight)
SECTION_PROMINENCE: Dict[str, float] = {
    "Top News": 0.55,
    "World": 0.50,
    "US News": 0.48,
    "Politics": 0.48,
    "Business": 0.45,
    "Technology": 0.45,
    "Science": 0.45,
    "Health": 0.45,
    "Sports": 0.40,
    "Entertainment": 0.38,
    "Oddities": 0.30,
    "Lifestyle": 0.35,
}

# Prominent AP journalists — byline reputation boost
PROMINENT_AUTHORS: Set[str] = {
    "zeke miller", "josh boak", "jill colvin", "aamer madhani",
    "lisa mascaro", "mary clare jalonick", "matthew lee",
    "lolita baldor", "ellen knickmeyer", "seth borenstein",
    "matt o'brien", "david rising", "fatima hussein",
    "colleen long", "will weissert", "steve peoples",
    "david bauder", "michael balsamo", "eric tucker",
    "mike stobbe", "lindsey tanner",
}

# Two-tier keyword categories — specific categories checked first
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "chatbot", "openai", "gpt", "llm", "generative ai", "chatgpt", "copilot",
        "anthropic", "claude", "gemini ai", "ai model", "language model", "ai safety",
        "autonomous", "computer vision", "robotics", "robot",
    ],
    "security": [
        "cybersecurity", "cyber attack", "hack", "ransomware", "data breach",
        "malware", "phishing", "vulnerability", "zero-day", "encryption",
        "surveillance", "privacy", "espionage", "cyber", "nsa", "fbi",
    ],
    "crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "crypto", "blockchain",
        "defi", "nft", "web3", "stablecoin", "binance", "coinbase",
    ],
    "health": [
        "covid", "vaccine", "pandemic", "disease", "cancer", "fda",
        "drug", "clinical trial", "mental health", "opioid", "virus",
        "outbreak", "cdc", "who health", "hospital", "medical",
    ],
    "science": [
        "nasa", "climate change", "global warming", "species", "fossil",
        "telescope", "asteroid", "earthquake", "hurricane", "genome",
        "evolution", "physics", "chemistry", "biology", "marine",
    ],
    "business": [
        "stock", "market", "economy", "inflation", "fed", "interest rate",
        "gdp", "trade", "tariff", "merger", "acquisition", "ipo",
        "earnings", "revenue", "layoff", "recession", "bank",
    ],
    "world": [
        "ukraine", "russia", "china", "nato", "un ", "united nations",
        "middle east", "gaza", "israel", "taiwan", "north korea",
        "refugee", "migration", "diplomatic", "sanctions", "treaty",
    ],
    "culture": [
        "oscar", "grammy", "emmy", "tony award", "netflix", "disney",
        "streaming", "box office", "album", "concert", "festival",
        "celebrity", "broadway", "movie", "film", "television",
    ],
    "education": [
        "school", "university", "college", "student", "teacher",
        "education", "campus", "tuition", "academic", "graduation",
    ],
    "environment": [
        "climate", "emissions", "carbon", "renewable", "solar", "wind energy",
        "pollution", "wildfire", "drought", "flood", "deforestation",
        "endangered", "conservation", "epa", "clean energy",
    ],
    "gaming": [
        "video game", "gaming", "esports", "playstation", "xbox",
        "nintendo", "steam", "twitch",
    ],
    "design": [
        "design", "ux", "user experience", "typography", "architecture",
    ],
}

# Categories that get a quality boost when detected via keywords
BOOSTED_CATEGORIES: Set[str] = {"ai", "security", "crypto", "environment"}


def _detect_category(title: str, summary: str, section_category: str) -> str:
    """Two-tier category detection: specific keywords first, then section fallback."""
    text = f"{title} {summary}".lower()
    matches: Dict[str, int] = {}
    for cat, keywords in KEYWORD_CATEGORIES.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > 0:
            matches[cat] = count
    if matches:
        # Prefer specific categories over section fallback
        best = max(matches, key=lambda c: (matches[c], c in BOOSTED_CATEGORIES))
        return best
    return section_category


def _compute_quality(
    section: str,
    position: int,
    category: str,
    author: str,
) -> float:
    """Quality score 0–1 based on section prominence, position, author, and category."""
    base = SECTION_PROMINENCE.get(section, 0.35)

    # Position decay within section — first articles score higher
    decay = 1.0 / (1.0 + 0.05 * position)
    score = base * decay

    # Prominent author boost
    if author and author.lower().strip() in PROMINENT_AUTHORS:
        score = min(1.0, score + 0.12)

    # Boosted category bonus
    if category in BOOSTED_CATEGORIES:
        score = min(1.0, score + 0.08)

    return round(min(1.0, score), 3)


class APNewsSource(BaseSource):
    """Crawl AP News section RSS feeds via RSSHub mirror.

    Parameters
    ----------
    sections : list[str] | None
        Which sections to include. None = all.
    limit : int
        Max articles per section feed. Default 15.
    min_quality : float
        Minimum quality score (0–1) to include an article.
    category_filter : list[str] | None
        Only include articles matching these categories.
    exclude_sections : list[str] | None
        Sections to skip.
    global_limit : int | None
        Max total articles returned (quality-sorted).
    """

    name = "apnews"

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
        url = feed_info["url"]
        section = feed_info["section"]
        section_category = feed_info["category"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for position, entry in enumerate(parsed.entries[: self.limit]):
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            # Cross-section deduplication
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Parse summary
            summary_raw = entry.get("summary", "").strip()
            summary_clean = ""
            if summary_raw:
                summary_clean = re.sub(r"<[^>]+>", "", summary_raw).strip()
                if len(summary_clean) > 300:
                    summary_clean = summary_clean[:297] + "..."

            # Parse timestamp
            ts = None
            for date_field in ("published", "updated"):
                raw = entry.get(date_field)
                if raw:
                    try:
                        ts = dateparser.parse(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            author = entry.get("author", "").strip()

            # Category detection
            category = _detect_category(title, summary_clean, section_category)

            # Category filter
            if self.category_filter and category not in self.category_filter:
                continue

            # Quality scoring
            quality = _compute_quality(section, position, category, author)
            if quality < self.min_quality:
                continue

            # Build rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 {section}")
            if summary_clean:
                parts.append(summary_clean)
            rich_summary = " · ".join(parts[:2])
            if summary_clean:
                rich_summary += f" — {summary_clean}"

            # Build tags
            tags = [
                f"apnews:section:{section.lower().replace(' ', '-')}",
                f"apnews:category:{category}",
            ]
            if author:
                tags.append(f"apnews:author:{author.lower().strip()}")
                if author.lower().strip() in PROMINENT_AUTHORS:
                    tags.append("apnews:prominent-author")

            articles.append(Article(
                title=title,
                url=link,
                source=f"AP News ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = AP_FEEDS

        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"].lower() not in self.exclude_sections]

        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[AP News] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[AP News] Failed to parse {feed_info['section']}: {e}")

        # Sort by quality (best first) and apply global limit
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)
        if self.global_limit:
            all_articles = all_articles[: self.global_limit]

        logger.info(f"[AP News] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
