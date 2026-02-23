"""Axios source — smart brevity news across tech, politics, business, and more.

Axios is known for concise, high-signal reporting. Free RSS feeds,
no API key required.

Enhanced features:
- 12 section feeds (was 9): added Sports, Climate, Local
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on section prominence, position decay, keyword specificity, and author reputation
- Prominent author recognition (15 Axios journalists/editors)
- Cross-section URL deduplication
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with ✍️ author and 📰 section
- Provenance tags: axios:section, axios:category, axios:author, axios:prominent-author, axios:tag
- Quality-sorted output
"""
import logging
import re
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

AXIOS_FEEDS = [
    {"url": "https://api.axios.com/feed/", "section": "Top Stories", "category": "world"},
    {"url": "https://api.axios.com/feed/technology/", "section": "Technology", "category": "tech"},
    {"url": "https://api.axios.com/feed/politics/", "section": "Politics", "category": "world"},
    {"url": "https://api.axios.com/feed/business/", "section": "Business", "category": "business"},
    {"url": "https://api.axios.com/feed/science/", "section": "Science", "category": "science"},
    {"url": "https://api.axios.com/feed/health/", "section": "Health", "category": "health"},
    {"url": "https://api.axios.com/feed/energy-environment/", "section": "Energy & Environment", "category": "environment"},
    {"url": "https://api.axios.com/feed/world/", "section": "World", "category": "world"},
    {"url": "https://api.axios.com/feed/media-trends/", "section": "Media", "category": "culture"},
    {"url": "https://api.axios.com/feed/sports/", "section": "Sports", "category": "culture"},
    {"url": "https://api.axios.com/feed/climate/", "section": "Climate", "category": "environment"},
    {"url": "https://api.axios.com/feed/local/", "section": "Local", "category": "world"},
]

# Section → default Clawler category mapping
SECTION_CATEGORY_MAP: Dict[str, str] = {
    f["section"].lower(): f["category"] for f in AXIOS_FEEDS
}

# Section prominence scores (editorial weight)
SECTION_PROMINENCE: Dict[str, float] = {
    "top stories": 0.60,
    "technology": 0.55,
    "politics": 0.55,
    "business": 0.50,
    "science": 0.50,
    "health": 0.50,
    "energy & environment": 0.48,
    "world": 0.55,
    "media": 0.45,
    "sports": 0.42,
    "climate": 0.48,
    "local": 0.40,
}

# Prominent Axios authors (senior reporters and editors)
PROMINENT_AUTHORS: Dict[str, float] = {
    "mike allen": 0.12,
    "jim vandehei": 0.12,
    "jonathan swan": 0.12,
    "sara fischer": 0.10,
    "dan primack": 0.10,
    "ina fried": 0.10,
    "scott rosenberg": 0.08,
    "jennifer a. kingson": 0.08,
    "margaret talev": 0.08,
    "hans nichols": 0.08,
    "andrew freedman": 0.08,
    "sam baker": 0.08,
    "dion rabouin": 0.08,
    "alex thompson": 0.08,
    "ryan heath": 0.08,
}

# --- Keyword category detection ---
SPECIFIC_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "chatgpt", "openai", "gpt-4", "gpt-5", "llm", "large language model",
        "generative ai", "copilot", "anthropic", "claude", "gemini ai",
        "computer vision", "natural language", "robotics", "autonomous",
        "stable diffusion", "midjourney", "training data", "transformer model",
    ],
    "security": [
        "cybersecurity", "cyber attack", "ransomware", "data breach", "hacking",
        "malware", "phishing", "zero-day", "vulnerability", "encryption",
        "surveillance", "privacy breach", "espionage", "exploit", "backdoor",
        "password", "authentication", "spyware", "botnet", "ddos",
    ],
    "crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "blockchain", "defi",
        "stablecoin", "crypto exchange", "nft", "web3", "digital currency",
        "crypto regulation", "token", "solana", "binance",
    ],
    "health": [
        "pandemic", "vaccine", "clinical trial", "fda", "disease",
        "drug", "pharmaceutical", "biotech", "cancer", "mental health",
        "public health", "healthcare", "hospital", "virus", "antibiotic",
        "obesity", "diabetes", "who", "cdc", "opioid",
    ],
    "science": [
        "climate change", "global warming", "nasa", "space launch", "satellite",
        "quantum computing", "physics", "biology", "genome", "crispr",
        "research study", "scientific", "spacex", "asteroid", "exoplanet",
        "fusion", "telescope", "mars", "jwst", "emissions",
    ],
    "business": [
        "earnings", "revenue", "ipo", "merger", "acquisition", "stock market",
        "antitrust", "monopoly", "ftc", "doj", "regulation", "lawsuit",
        "venture capital", "layoffs", "valuation", "wall street", "gdp",
        "inflation", "recession", "interest rate", "federal reserve",
    ],
    "environment": [
        "carbon emissions", "renewable energy", "solar power", "wind energy",
        "climate crisis", "sustainability", "pollution", "deforestation",
        "biodiversity", "conservation", "electric vehicle", "ev", "clean energy",
        "net zero", "greenhouse gas", "wildfire", "drought", "sea level",
    ],
    "world": [
        "war", "conflict", "sanctions", "diplomacy", "election",
        "government", "congress", "senate", "white house", "eu", "china",
        "nato", "united nations", "refugee", "immigration", "geopolitics",
    ],
    "culture": [
        "movie", "film", "tv show", "streaming", "netflix", "disney",
        "book review", "music", "art", "documentary", "social media",
        "tiktok", "instagram", "creator economy",
    ],
    "gaming": [
        "video game", "gaming", "esports", "playstation", "xbox", "nintendo",
        "game studio", "steam", "pc gaming", "console", "indie game",
    ],
    "education": [
        "university", "college", "student", "teacher", "education",
        "school", "tuition", "academic", "scholarship", "campus",
    ],
    "design": [
        "user experience", "ux design", "ui design", "product design",
        "graphic design", "accessibility", "interface", "typography",
    ],
}

# Categories that get a specificity boost in quality scoring
BOOSTED_CATEGORIES = {"ai", "security", "crypto", "environment", "health"}


def _detect_category(title: str, summary: str, section_category: str) -> str:
    """Two-tier category detection: specific keywords first, then section fallback."""
    text = f"{title} {summary}".lower()
    best_cat = None
    best_hits = 0
    for cat, keywords in SPECIFIC_CATEGORIES.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    if best_cat and best_hits >= 1:
        return best_cat
    return section_category


def _compute_quality(
    section: str,
    category: str,
    section_category: str,
    position: int,
    author: str,
) -> float:
    """Quality score (0–1) based on section prominence, position, keyword specificity, and author."""
    base = SECTION_PROMINENCE.get(section.lower(), 0.42)
    # Position decay: first articles score higher
    position_factor = 1.0 / (1.0 + 0.05 * position)
    score = base * position_factor
    # Boost for specific keyword-detected category (not just section fallback)
    if category != section_category and category in BOOSTED_CATEGORIES:
        score = min(1.0, score + 0.10)
    elif category != section_category:
        score = min(1.0, score + 0.05)
    # Author reputation boost
    author_boost = PROMINENT_AUTHORS.get(author.lower().strip(), 0.0)
    score = min(1.0, score + author_boost)
    return round(min(1.0, score), 3)


class AxiosSource(BaseSource):
    """Fetch articles from Axios RSS feeds.

    Parameters
    ----------
    limit : int
        Max articles per feed. Default 20.
    sections : list of str or None
        Section names to crawl. None = all sections.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    exclude_sections : list of str or None
        Exclude these sections.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "axios"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        limit: int = 20,
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

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        feeds = AXIOS_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]
        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"].lower() not in self.exclude_sections]

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info("[Axios] %s: %d articles", feed_info["section"], len(articles))
            except Exception as exc:
                logger.warning("[Axios] Failed to parse %s: %s", feed_info["section"], exc)

        # Apply filters
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if (a.quality_score or 0) >= self.min_quality]

        if self.category_filter:
            all_articles = [a for a in all_articles if a.category in self.category_filter]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Global limit
        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info("[Axios] Total: %d articles from %d sections", len(all_articles), len(feeds))
        return all_articles

    def _parse_feed(self, feed_info: dict, seen: Set[str]) -> List[Article]:
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

            # Cross-section URL deduplication
            if link in seen:
                continue
            seen.add(link)

            summary = entry.get("summary", entry.get("description", "")).strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    # Truncate at sentence boundary
                    trunc = summary[:300]
                    last_period = trunc.rfind(".")
                    if last_period > 150:
                        summary = trunc[: last_period + 1]
                    else:
                        summary = trunc.rstrip() + "..."

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

            # Two-tier category detection
            category = _detect_category(title, summary, section_category)
            quality = _compute_quality(section, category, section_category, position, author)

            # Build rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 {section}")
            rich_summary = " · ".join(parts)
            if summary:
                rich_summary += f" — {summary}"

            # Provenance tags
            section_tag = section.lower().replace(" ", "_").replace("&", "and")
            tags = [
                f"axios:section:{section_tag}",
                f"axios:category:{category}",
            ]
            if author:
                tags.append(f"axios:author:{author.lower().strip()}")
                if author.lower().strip() in PROMINENT_AUTHORS:
                    tags.append("axios:prominent-author")

            # Extract RSS category tags
            for tag_entry in entry.get("tags", []):
                term = tag_entry.get("term", "").strip().lower()
                if term:
                    tags.append(f"axios:tag:{term}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"Axios ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles
