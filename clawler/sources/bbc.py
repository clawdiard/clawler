"""BBC News source — fetches articles from BBC RSS feeds.

BBC News is one of the world's most trusted and comprehensive news
services with free RSS feeds covering all major sections and regional editions.
No API key required.

Enhanced v10.34: keyword categories, quality scoring, regional feeds,
author extraction, filters, provenance tags.
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

# ── Section feeds ──────────────────────────────────────────────────
BBC_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/rss.xml", "section": "top_stories", "label": "Top Stories", "category": "general", "prominence": 0.55},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "section": "world", "label": "World", "category": "world", "prominence": 0.50},
    {"url": "https://feeds.bbci.co.uk/news/uk/rss.xml", "section": "uk", "label": "UK", "category": "world", "prominence": 0.45},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml", "section": "business", "label": "Business", "category": "business", "prominence": 0.48},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "section": "technology", "label": "Technology", "category": "tech", "prominence": 0.50},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "section": "science", "label": "Science & Environment", "category": "science", "prominence": 0.50},
    {"url": "https://feeds.bbci.co.uk/news/health/rss.xml", "section": "health", "label": "Health", "category": "health", "prominence": 0.48},
    {"url": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml", "section": "entertainment", "label": "Entertainment & Arts", "category": "culture", "prominence": 0.42},
    {"url": "https://feeds.bbci.co.uk/news/politics/rss.xml", "section": "politics", "label": "Politics", "category": "world", "prominence": 0.45},
    {"url": "https://feeds.bbci.co.uk/news/education/rss.xml", "section": "education", "label": "Education", "category": "education", "prominence": 0.40},
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml", "section": "sport", "label": "Sport", "category": "sports", "prominence": 0.42},
    {"url": "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "section": "africa", "label": "Africa", "category": "world", "prominence": 0.40},
    {"url": "https://feeds.bbci.co.uk/news/world/asia/rss.xml", "section": "asia", "label": "Asia", "category": "world", "prominence": 0.42},
    {"url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "section": "europe", "label": "Europe", "category": "world", "prominence": 0.42},
    {"url": "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml", "section": "latin_america", "label": "Latin America", "category": "world", "prominence": 0.40},
    {"url": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "section": "middle_east", "label": "Middle East", "category": "world", "prominence": 0.42},
    {"url": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "section": "us_canada", "label": "US & Canada", "category": "world", "prominence": 0.45},
]

# ── Keyword → category (specific over generic) ────────────────────
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "chatbot", "openai", "chatgpt", "gpt-4", "llm", "generative ai", "copilot",
        "deepmind", "anthropic", "gemini ai", "large language", "diffusion model",
        "ai model", "ai safety", "computer vision", "natural language",
    ],
    "security": [
        "cybersecurity", "cyber attack", "ransomware", "malware", "hacking", "data breach",
        "phishing", "zero-day", "vulnerability", "encryption", "surveillance", "spyware",
        "gchq", "mi5", "mi6", "national security", "cyber crime",
    ],
    "crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "blockchain", "nft", "defi",
        "crypto exchange", "stablecoin", "web3", "digital currency",
    ],
    "health": [
        "nhs", "hospital", "vaccine", "pandemic", "disease", "cancer", "mental health",
        "drug", "treatment", "clinical trial", "dementia", "alzheimer", "obesity",
        "diabetes", "virus", "infection", "antibiotic", "surgery",
    ],
    "science": [
        "climate change", "global warming", "fossil fuel", "renewable energy", "solar",
        "nasa", "space", "asteroid", "telescope", "physics", "quantum", "genome",
        "evolution", "species", "ocean", "biodiversity", "crispr", "fusion",
    ],
    "business": [
        "stock market", "ftse", "dow jones", "inflation", "interest rate", "bank of england",
        "federal reserve", "gdp", "recession", "ipo", "merger", "acquisition",
        "profit", "revenue", "startup", "venture capital",
    ],
    "world": [
        "united nations", "nato", "european union", "war", "conflict", "refugee",
        "sanctions", "diplomacy", "summit", "election", "protest", "coup",
    ],
    "culture": [
        "film", "movie", "oscar", "bafta", "grammy", "album", "exhibition",
        "gallery", "theatre", "novel", "book", "festival", "streaming",
    ],
    "gaming": [
        "video game", "playstation", "xbox", "nintendo", "esports", "gaming",
        "steam", "game developer",
    ],
    "design": [
        "design", "ux", "user experience", "typography", "graphic design",
        "architecture", "interior design",
    ],
    "education": [
        "university", "school", "student", "teacher", "gcse", "a-level",
        "exam", "tuition", "curriculum", "ofsted",
    ],
    "environment": [
        "pollution", "emissions", "deforestation", "conservation", "recycling",
        "net zero", "carbon", "plastic", "wildlife", "endangered",
    ],
}

# Prominent BBC journalists (quality boost)
PROMINENT_AUTHORS = {
    "amol rajan", "laura kuenssberg", "ros atkins", "nick robinson",
    "faisal islam", "katya adler", "lyse doucet", "clive myrie",
    "mishal husain", "huw edwards", "fergus walsh", "rory cellan-jones",
    "zoe kleinman", "chris mason", "mark easton", "andrew marr",
}


def _detect_category(title: str, summary: str, section_category: str) -> str:
    """Two-tier keyword detection: specific categories first, then section fallback."""
    text = f"{title} {summary}".lower()
    for cat, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return section_category


def _quality_score(prominence: float, position: int, author: str, category: str) -> float:
    """Compute quality score 0–1.

    Factors: section prominence × position decay + author boost + category boost.
    """
    # Position decay: first article gets full prominence, decays logarithmically
    pos_factor = 1.0 / (1.0 + 0.15 * math.log1p(position))
    score = prominence * pos_factor

    # Author reputation boost
    if author.lower().strip() in PROMINENT_AUTHORS:
        score = min(1.0, score + 0.10)

    # Specific category boost (more valuable than generic)
    if category in ("ai", "security", "crypto", "environment"):
        score = min(1.0, score + 0.05)

    return round(score, 3)


def _fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class BBCNewsSource(BaseSource):
    """Crawl BBC News RSS feeds.

    Parameters
    ----------
    sections : list[str] | None
        Which sections to include (by section key). None = all.
    exclude_sections : list[str] | None
        Sections to exclude.
    limit : int
        Max articles per section feed. Default 15.
    global_limit : int | None
        Max total articles (quality-sorted). None = unlimited.
    min_quality : float
        Minimum quality score (0–1). Default 0.
    category_filter : list[str] | None
        Only return articles matching these categories.
    """

    name = "bbc"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        limit: int = 15,
        global_limit: Optional[int] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
    ):
        self.sections = [s.lower() for s in sections] if sections else None
        self.exclude_sections = {s.lower() for s in (exclude_sections or [])}
        self.limit = limit
        self.global_limit = global_limit
        self.min_quality = min_quality
        self.category_filter = {c.lower() for c in (category_filter or [])} or None

    def _select_feeds(self) -> List[dict]:
        feeds = BBC_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"] in self.sections]
        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"] not in self.exclude_sections]
        return feeds

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        label = feed_info["label"]
        section_category = feed_info["category"]
        prominence = feed_info["prominence"]

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
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Summary
            summary = entry.get("summary", entry.get("description", "")).strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            # Timestamp
            ts = None
            for date_field in ("published", "updated"):
                raw = entry.get(date_field)
                if raw:
                    try:
                        ts = dateparser.parse(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            # Author
            author = entry.get("author", "").strip()

            # Category detection
            category = _detect_category(title, summary or "", section_category)

            # Quality score
            quality = _quality_score(prominence, position, author, category)

            # Filters
            if quality < self.min_quality:
                continue
            if self.category_filter and category not in self.category_filter:
                continue

            # Rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 {label}")
            if summary:
                parts.append(summary)
            rich_summary = " · ".join(parts[:2])
            if summary:
                rich_summary += f" — {summary}"

            # Provenance tags
            tags = [
                f"bbc:section:{section}",
                f"bbc:category:{category}",
            ]
            if author:
                tags.append(f"bbc:author:{author.lower().strip()}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"BBC News ({label})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = self._select_feeds()
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[BBC] {feed_info['label']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[BBC] Failed to parse {feed_info['label']}: {e}")

        # Sort by quality, best first
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        if self.global_limit:
            all_articles = all_articles[: self.global_limit]

        logger.info(f"[BBC] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
