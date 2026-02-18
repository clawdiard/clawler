"""Reuters source — fetches articles from Reuters RSS feeds.

Reuters is one of the world's most trusted wire services, providing
high-quality breaking news across multiple sections. Free RSS feeds
are available at reuters.com.

Enhanced features:
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on section prominence + keyword specificity
- Multi-region support via `regions` param
- Cross-section/region URL deduplication
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with ✍️ author and 📰 section
- Provenance tags: reuters:section, reuters:region, reuters:category, reuters:author
"""
import logging
import math
import re
from datetime import datetime
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

# Reuters RSS feeds (free, no key required)
REUTERS_FEEDS = [
    {"url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "section": "Business", "category": "business"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best", "section": "Technology", "category": "tech"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best", "section": "Politics", "category": "world"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=environment&post_type=best", "section": "Environment", "category": "science"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=health&post_type=best", "section": "Health", "category": "health"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=sports&post_type=best", "section": "Sports", "category": "sports"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=lifestyle-entertainment&post_type=best", "section": "Lifestyle", "category": "culture"},
    {"url": "https://www.reutersagency.com/feed/?taxonomy=best-regions&post_type=best", "section": "World", "category": "world"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=deals&post_type=best", "section": "Deals", "category": "business"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=government&post_type=best", "section": "Government", "category": "world"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=media-telecom&post_type=best", "section": "Media", "category": "tech"},
    {"url": "https://www.reutersagency.com/feed/?best-topics=aerospace-defense&post_type=best", "section": "Aerospace", "category": "science"},
]

# Regional feeds
REUTERS_REGIONS = {
    "us": "https://www.reutersagency.com/feed/?taxonomy=best-regions&best-region=north-america&post_type=best",
    "europe": "https://www.reutersagency.com/feed/?taxonomy=best-regions&best-region=europe&post_type=best",
    "asia": "https://www.reutersagency.com/feed/?taxonomy=best-regions&best-region=asia&post_type=best",
    "africa": "https://www.reutersagency.com/feed/?taxonomy=best-regions&best-region=africa&post_type=best",
    "middle_east": "https://www.reutersagency.com/feed/?taxonomy=best-regions&best-region=middle-east&post_type=best",
    "latam": "https://www.reutersagency.com/feed/?taxonomy=best-regions&best-region=latin-america&post_type=best",
}

# Section prominence scores (Reuters editorial weight)
SECTION_PROMINENCE: Dict[str, float] = {
    "World": 0.55,
    "Business": 0.50,
    "Technology": 0.50,
    "Politics": 0.50,
    "Environment": 0.45,
    "Health": 0.45,
    "Aerospace": 0.45,
    "Government": 0.45,
    "Media": 0.40,
    "Deals": 0.40,
    "Sports": 0.35,
    "Lifestyle": 0.35,
}

# --- Keyword category detection ---
# Two-tier: specific categories checked first, then section fallback
SPECIFIC_CATEGORIES = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "chatgpt", "openai", "gpt-4", "gpt-5", "llm", "large language model",
        "generative ai", "copilot", "anthropic", "claude", "gemini ai",
        "computer vision", "natural language", "autonomous", "robotics",
    ],
    "security": [
        "cybersecurity", "cyber attack", "ransomware", "data breach", "hacking",
        "malware", "phishing", "zero-day", "vulnerability", "encryption",
        "surveillance", "privacy breach", "espionage", "cyberwarfare",
    ],
    "crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "blockchain", "defi",
        "stablecoin", "crypto exchange", "nft", "web3", "digital currency",
        "cbdc", "central bank digital",
    ],
    "health": [
        "pandemic", "vaccine", "clinical trial", "fda approval", "who health",
        "disease outbreak", "drug", "pharmaceutical", "biotech", "cancer treatment",
        "mental health", "public health", "healthcare", "hospital",
    ],
    "science": [
        "climate change", "global warming", "emissions", "renewable energy",
        "solar power", "wind energy", "nasa", "space launch", "satellite",
        "quantum computing", "physics", "biology", "genome", "crispr",
        "research study", "scientific",
    ],
    "business": [
        "earnings", "revenue", "ipo", "merger", "acquisition", "stock market",
        "wall street", "fed rate", "interest rate", "inflation", "recession",
        "gdp", "trade deficit", "tariff", "supply chain",
    ],
    "world": [
        "war", "conflict", "ceasefire", "sanctions", "diplomacy", "nato",
        "united nations", "refugee", "humanitarian", "election", "coup",
        "protest", "treaty",
    ],
    "culture": [
        "oscar", "grammy", "emmy", "box office", "streaming", "netflix",
        "disney", "concert", "festival", "museum", "art exhibition",
    ],
    "gaming": [
        "video game", "gaming", "esports", "playstation", "xbox", "nintendo",
        "game studio",
    ],
    "design": [
        "ux design", "user experience", "interface design", "graphic design",
        "industrial design", "architecture award",
    ],
    "education": [
        "university", "college", "student", "education policy", "school",
        "academic", "scholarship", "tuition",
    ],
    "environment": [
        "biodiversity", "deforestation", "pollution", "ocean", "wildlife",
        "endangered species", "conservation", "carbon neutral", "sustainability",
    ],
}


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


def _compute_quality(section: str, category: str, section_category: str, position: int) -> float:
    """Quality score (0–1) based on section prominence + position + keyword specificity."""
    base = SECTION_PROMINENCE.get(section, 0.40)
    # Position decay: first articles score higher
    position_factor = 1.0 / (1.0 + 0.05 * position)
    score = base * position_factor
    # Boost for specific keyword-detected category (not just section fallback)
    if category != section_category:
        score = min(1.0, score + 0.10)
    return round(min(1.0, score), 3)


def _fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class ReutersSource(BaseSource):
    """Crawl Reuters RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. None = all.
    regions : list of str or None
        Additional regional feeds to include.
        Options: us, europe, asia, africa, middle_east, latam.
    limit : int
        Max articles per feed. Default 15.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    exclude_sections : list of str or None
        Exclude these sections.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "reuters"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        limit: int = 15,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.sections = [s.lower() for s in sections] if sections else None
        self.regions = [r.lower() for r in regions] if regions else None
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None
        self.global_limit = global_limit

    def _parse_feed(self, feed_url: str, section: str, section_category: str, region: Optional[str] = None) -> List[Article]:
        """Parse a single Reuters RSS feed into articles."""
        content = self.fetch_url(feed_url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for position, entry in enumerate(parsed.entries[:self.limit]):
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            summary_raw = entry.get("summary", "").strip()
            summary_clean = ""
            if summary_raw:
                summary_clean = re.sub(r"<[^>]+>", "", summary_raw).strip()
                if len(summary_clean) > 300:
                    summary_clean = summary_clean[:297] + "..."

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

            # Two-tier category detection
            category = _detect_category(title, summary_clean, section_category)

            # Quality scoring
            quality = _compute_quality(section, category, section_category, position)

            # Build rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 {section}")
            if region:
                parts.append(f"🌍 {region.upper()}")
            if summary_clean:
                parts.append(summary_clean)
            rich_summary = " · ".join(parts[:3])
            if summary_clean and len(parts) > 3:
                rich_summary += f" — {summary_clean}"
            elif summary_clean and len(parts) <= 3 and summary_clean not in rich_summary:
                rich_summary += f" — {summary_clean}"

            # Provenance tags
            tags = [
                f"reuters:section:{section.lower()}",
                f"reuters:category:{category}",
            ]
            if author:
                tags.append(f"reuters:author:{author.lower()}")
            if region:
                tags.append(f"reuters:region:{region}")

            # Extract RSS category tags
            for tag_entry in entry.get("tags", []):
                term = tag_entry.get("term", "").strip().lower()
                if term:
                    tags.append(f"reuters:tag:{term}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"Reuters ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()

        # Select section feeds
        feeds = REUTERS_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]
        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"].lower() not in self.exclude_sections]

        all_articles = []

        # Section feeds
        for feed_info in feeds:
            try:
                articles = self._parse_feed(
                    feed_info["url"], feed_info["section"], feed_info["category"]
                )
                for a in articles:
                    if a.url not in seen_urls:
                        seen_urls.add(a.url)
                        all_articles.append(a)
                logger.info(f"[Reuters] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Reuters] Failed to parse {feed_info['section']}: {e}")

        # Regional feeds
        if self.regions:
            for region in self.regions:
                region_url = REUTERS_REGIONS.get(region)
                if not region_url:
                    logger.warning(f"[Reuters] Unknown region: {region}")
                    continue
                try:
                    articles = self._parse_feed(region_url, "World", "world", region=region)
                    for a in articles:
                        if a.url not in seen_urls:
                            seen_urls.add(a.url)
                            all_articles.append(a)
                    logger.info(f"[Reuters] Region {region}: {len(articles)} articles")
                except Exception as e:
                    logger.warning(f"[Reuters] Failed region {region}: {e}")

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

        logger.info(f"[Reuters] Total: {len(all_articles)} articles")
        return all_articles
