"""New York Times source — fetches articles from NYT RSS feeds.

The New York Times provides public RSS feeds across all major sections.
No API key required for RSS access.

Enhanced features:
- 18 section feeds (was 11): added Politics, Education, Movies, Travel, Real Estate, Magazine, Books
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on section prominence × position decay + author reputation
- Prominent journalist detection (20+ NYT journalists) with reputation boost
- Cross-section URL deduplication
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with ✍️ author · 📰 section · description
- Provenance tags: nytimes:section, nytimes:category, nytimes:author, nytimes:prominent-author
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

NYT_FEEDS = [
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "section": "Home", "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "section": "World", "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml", "section": "US", "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", "section": "Politics", "category": "world"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "section": "Business", "category": "business"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "section": "Technology", "category": "tech"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", "section": "Science", "category": "science"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml", "section": "Health", "category": "health"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml", "section": "Sports", "category": "sports"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml", "section": "Arts", "category": "culture"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml", "section": "Opinion", "category": "opinion"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml", "section": "Climate", "category": "science"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Education.xml", "section": "Education", "category": "education"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml", "section": "Movies", "category": "culture"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml", "section": "Travel", "category": "culture"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/RealEstate.xml", "section": "Real Estate", "category": "business"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Magazine.xml", "section": "Magazine", "category": "culture"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Books.xml", "section": "Books", "category": "culture"},
]

# Section prominence scores (editorial weight)
SECTION_PROMINENCE: Dict[str, float] = {
    "Home": 0.55, "World": 0.50, "US": 0.48, "Politics": 0.48,
    "Business": 0.45, "Technology": 0.50, "Science": 0.50, "Health": 0.45,
    "Sports": 0.35, "Arts": 0.40, "Opinion": 0.42, "Climate": 0.48,
    "Education": 0.40, "Movies": 0.38, "Travel": 0.35, "Real Estate": 0.35,
    "Magazine": 0.42, "Books": 0.38,
}

# Categories that get a quality boost when detected via keywords
BOOSTED_CATEGORIES: Set[str] = {"ai", "security", "crypto", "environment"}
BOOST_AMOUNT = 0.08

# Keyword → category mapping (specific categories checked first)
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": ["artificial intelligence", "openai", "chatgpt", "llm", "machine learning",
           "deep learning", "neural network", "generative ai", "gpt", "copilot",
           "anthropic", "gemini ai", "midjourney", "stable diffusion", "language model",
           "computer vision", "reinforcement learning", "transformer model"],
    "security": ["cybersecurity", "cyber attack", "ransomware", "data breach", "hacking",
                 "malware", "phishing", "zero-day", "encryption", "surveillance",
                 "national security", "espionage", "cyberwar", "privacy violation"],
    "crypto": ["bitcoin", "ethereum", "cryptocurrency", "blockchain", "crypto",
               "defi", "nft", "web3", "stablecoin", "mining crypto", "solana"],
    "health": ["pandemic", "vaccine", "cancer", "mental health", "drug approval",
               "clinical trial", "fda", "who health", "disease", "epidemic",
               "obesity", "alzheimer", "diabetes", "opioid", "public health"],
    "science": ["nasa", "climate change", "global warming", "quantum", "genome",
                "crispr", "fusion energy", "exoplanet", "telescope", "particle physics",
                "space station", "asteroid", "paleontology", "marine biology"],
    "business": ["wall street", "stock market", "federal reserve", "inflation",
                 "gdp", "recession", "ipo", "merger", "acquisition", "startup",
                 "venture capital", "earnings", "layoffs", "unemployment"],
    "world": ["ukraine", "middle east", "nato", "united nations", "sanctions",
              "refugee", "diplomacy", "foreign policy", "coup", "ceasefire",
              "humanitarian", "genocide", "territorial"],
    "culture": ["oscar", "grammy", "emmy", "tony award", "broadway", "netflix",
                "streaming", "box office", "bestseller", "exhibition", "museum",
                "fashion week", "met gala"],
    "education": ["student loan", "university", "college", "tuition", "scholarship",
                  "curriculum", "standardized test", "school board", "campus",
                  "higher education", "k-12", "admissions"],
    "environment": ["wildfire", "flooding", "drought", "carbon emission", "renewable",
                    "solar energy", "wind farm", "deforestation", "biodiversity",
                    "pollution", "epa", "conservation", "coral reef"],
    "gaming": ["video game", "playstation", "xbox", "nintendo", "esports",
               "game developer", "steam", "gaming industry"],
    "design": ["ux design", "user interface", "typography", "graphic design",
               "architecture", "industrial design", "product design"],
}

# Prominent NYT journalists — recognized for beat expertise
PROMINENT_AUTHORS: Dict[str, str] = {
    "david brooks": "opinion",
    "paul krugman": "opinion",
    "thomas friedman": "opinion",
    "maureen dowd": "opinion",
    "nicholas kristof": "opinion",
    "ross douthat": "opinion",
    "ezra klein": "opinion",
    "michelle goldberg": "opinion",
    "maggie haberman": "politics",
    "peter baker": "politics",
    "david leonhardt": "analysis",
    "cade metz": "tech",
    "kevin roose": "tech",
    "erin griffith": "tech",
    "karen weise": "tech",
    "carl zimmer": "science",
    "emily baumgaertner": "health",
    "apoorva mandavilli": "health",
    "andrew ross sorkin": "business",
    "dealbook": "business",
    "ben smith": "media",
    "a.o. scott": "culture",
    "wesley morris": "culture",
}

PROMINENT_AUTHOR_BOOST = 0.06


def _detect_category(title: str, summary: str) -> Optional[str]:
    """Detect specific category from title + summary keywords."""
    text = f"{title} {summary}".lower()
    for cat, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return None


def _format_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class NYTimesSource(BaseSource):
    """Crawl New York Times RSS feeds.

    Parameters
    ----------
    sections : list[str] | None
        Which sections to include (case-insensitive). None = all.
    exclude_sections : list[str] | None
        Sections to skip.
    limit : int
        Max articles per section feed. Default 15.
    global_limit : int | None
        Max total articles (quality-sorted). None = unlimited.
    min_quality : float
        Minimum quality score threshold (0–1). Default 0.0.
    category_filter : list[str] | None
        Only return articles matching these categories.
    """

    name = "nytimes"

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
        self.exclude_sections = {s.lower() for s in exclude_sections} if exclude_sections else set()
        self.limit = limit
        self.global_limit = global_limit
        self.min_quality = min_quality
        self.category_filter = {c.lower() for c in category_filter} if category_filter else None

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        default_category = feed_info["category"]
        base_prominence = SECTION_PROMINENCE.get(section, 0.40)

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for idx, entry in enumerate(parsed.entries[:self.limit]):
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            # Dedup across sections
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Summary
            summary_raw = entry.get("summary", "").strip()
            summary = re.sub(r"<[^>]+>", "", summary_raw).strip() if summary_raw else ""
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

            # Category detection: keywords first, then section default
            detected = _detect_category(title, summary)
            category = detected or default_category

            # Quality scoring: prominence × position decay + author boost
            position_decay = 1.0 / (1.0 + math.log1p(idx))
            quality = base_prominence * position_decay

            # Prominent author boost
            is_prominent = False
            if author:
                author_lower = author.lower()
                for pa_name in PROMINENT_AUTHORS:
                    if pa_name in author_lower:
                        quality += PROMINENT_AUTHOR_BOOST
                        is_prominent = True
                        break

            # Boosted category bonus
            if category in BOOSTED_CATEGORIES:
                quality += BOOST_AMOUNT

            quality = min(quality, 1.0)

            # Filters
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
                f"nytimes:section:{section.lower().replace(' ', '-')}",
                f"nytimes:category:{category}",
            ]
            if author:
                tags.append(f"nytimes:author:{author.lower().replace(' ', '-')}")
            if is_prominent:
                tags.append("nytimes:prominent-author")

            # RSS category tags
            for tag_entry in entry.get("tags", []):
                term = tag_entry.get("term", "").strip()
                if term:
                    tags.append(f"nytimes:tag:{term.lower().replace(' ', '-')}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"NYT ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                quality_score=quality,
                author=author,
                tags=tags,
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = NYT_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]
        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"].lower() not in self.exclude_sections]

        all_articles = []
        seen_urls: Set[str] = set()

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[NYT] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[NYT] Failed to parse {feed_info['section']}: {e}")

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        # Global limit
        if self.global_limit and len(all_articles) > self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[NYT] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
