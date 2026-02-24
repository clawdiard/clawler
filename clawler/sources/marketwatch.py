"""MarketWatch source — fetches articles from MarketWatch RSS feeds.

MarketWatch (Dow Jones) provides stock market, financial, and business news.
Free RSS feeds are available at marketwatch.com.

Enhanced features:
- 8 section feeds (was 5): added Real Estate, Retirement, Bonds/Rates
- Quality scoring (0–1) based on section prominence × position decay + keyword boost
- Two-tier keyword category detection (8 specific finance subcategories)
- Cross-feed URL deduplication
- Filters: min_quality, category_filter, global_limit
- Rich summaries with 📊 section · description
- Provenance tags: marketwatch:section, marketwatch:category
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

# Section feeds with prominence weights
MARKETWATCH_FEEDS = [
    {"url": "http://feeds.marketwatch.com/marketwatch/topstories/", "section": "Top Stories", "category": "business", "prominence": 1.0},
    {"url": "http://feeds.marketwatch.com/marketwatch/realtimeheadlines/", "section": "Breaking", "category": "business", "prominence": 0.95},
    {"url": "http://feeds.marketwatch.com/marketwatch/marketpulse/", "section": "Market Pulse", "category": "business", "prominence": 0.90},
    {"url": "http://feeds.marketwatch.com/marketwatch/software/", "section": "Software", "category": "tech", "prominence": 0.80},
    {"url": "http://feeds.marketwatch.com/marketwatch/pf/", "section": "Personal Finance", "category": "business", "prominence": 0.75},
    {"url": "http://feeds.marketwatch.com/marketwatch/realestate/", "section": "Real Estate", "category": "business", "prominence": 0.72},
    {"url": "http://feeds.marketwatch.com/marketwatch/retirement/", "section": "Retirement", "category": "business", "prominence": 0.68},
    {"url": "http://feeds.marketwatch.com/marketwatch/bondsandrates/", "section": "Bonds & Rates", "category": "business", "prominence": 0.82},
]

# Keyword quality tiers
_KEYWORD_TIERS: Dict[str, Dict[str, float]] = {
    "high": {
        "keywords": ["earnings", "fed ", "federal reserve", "market crash", "billion",
                      "ipo", "acquisition", "gdp", "inflation", "interest rate",
                      "recession", "merger", "sec ", "bankruptcy"],
        "boost": 0.10,
    },
    "medium": {
        "keywords": ["stock", "investor", "wall street", "s&p 500", "dow jones",
                      "revenue", "profit", "growth", "dividend", "nasdaq",
                      "cryptocurrency", "bitcoin", "etf"],
        "boost": 0.05,
    },
}

# Category refinement keywords
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "tech": ["ai ", "artificial intelligence", "software", "tech", "crypto", "bitcoin", "blockchain", "cybersecurity"],
    "security": ["hack", "breach", "fraud", "scam", "sec enforcement"],
    "world": ["china", "europe", "trade war", "tariff", "sanctions", "opec", "global"],
    "science": ["climate", "energy", "renewable", "ev ", "electric vehicle"],
}


def _position_decay(index: int, total: int) -> float:
    """Position-based decay: top articles score higher. Returns 0.6–1.0."""
    if total <= 1:
        return 1.0
    return 1.0 - 0.4 * (index / (total - 1))


def _keyword_boost(title: str, summary: str) -> float:
    """Compute keyword-based quality boost (highest tier wins)."""
    text = f"{title} {summary}".lower()
    for tier_data in [_KEYWORD_TIERS["high"], _KEYWORD_TIERS["medium"]]:
        if any(kw in text for kw in tier_data["keywords"]):
            return tier_data["boost"]
    return 0.0


def _compute_quality(prominence: float, position: int, total: int,
                     kw_boost: float) -> float:
    """Compute quality score from section prominence × position + keyword boost."""
    base = prominence * _position_decay(position, total)
    return min(1.0, round(base * 0.60 + 0.22 + kw_boost, 4))


class MarketWatchSource(BaseSource):
    """Crawl MarketWatch RSS feeds with quality scoring and category detection.

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

    name = "marketwatch"

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
            kw_boost = _keyword_boost(title, summary)
            refined_category = self._refine_category(category, title, summary)
            quality = _compute_quality(prominence, idx, total, kw_boost)

            if quality < self.min_quality:
                continue
            if self.category_filter and refined_category != self.category_filter:
                continue

            # Rich summary
            parts = [f"📊 {section}"]
            if author:
                parts.insert(0, f"✍️ {author}")
            if summary:
                parts.append(summary)
            rich_summary = " · ".join(parts)

            tags = [f"marketwatch:{section.lower().replace(' ', '_').replace('&', 'and')}",
                    f"marketwatch:{refined_category}"]
            if author:
                tags.append(f"marketwatch:author:{author.lower().strip()}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"MarketWatch ({section})",
                summary=rich_summary,
                timestamp=ts,
                category=refined_category,
                quality_score=quality,
                author=author,
                tags=tags,
            ))

        return articles

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        feeds = MARKETWATCH_FEEDS
        if self.sections:
            feeds = [f for f in feeds if f["section"].lower() in self.sections]

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[MarketWatch] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[MarketWatch] Failed to parse {feed_info['section']}: {e}")

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[MarketWatch] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
