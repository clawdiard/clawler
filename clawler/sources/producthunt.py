"""ProductHunt source — trending products via RSS (no key needed).

Enhanced features:
- Quality scoring (0–1) based on position rank, keyword specificity, category confidence, hunter reputation
- Author/hunter extraction with prominent hunter recognition
- Direct product link extraction from content HTML
- Keyword-based category detection from title + summary (14 categories)
- Filters: min_quality, category_filter
- Rich tags (author, category, quality)
- Quality-sorted output
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

PRODUCTHUNT_FEED = "https://www.producthunt.com/feed"

# Keyword → category mapping for product classification
KEYWORD_CATEGORY_MAP: Dict[str, str] = {
    # AI / ML
    "ai": "ai", "gpt": "ai", "llm": "ai", "chatgpt": "ai", "claude": "ai",
    "copilot": "ai", "machine learning": "ai", "neural": "ai", "deep learning": "ai",
    "artificial intelligence": "ai", "openai": "ai", "generative": "ai", "diffusion": "ai",
    "model": "ai", "prompt": "ai", "agent": "ai", "mcp": "ai",
    # Design
    "design": "design", "figma": "design", "ui": "design", "ux": "design",
    "illustration": "design", "logo": "design", "font": "design", "color": "design",
    "wireframe": "design", "prototype": "design", "icon": "design",
    # Developer tools
    "api": "tech", "developer": "tech", "code": "tech", "sdk": "tech",
    "devtool": "tech", "cli": "tech", "github": "tech", "git": "tech",
    "database": "tech", "deploy": "tech", "docker": "tech", "serverless": "tech",
    "ide": "tech", "debug": "tech", "terminal": "tech", "compiler": "tech",
    # Productivity
    "productivity": "business", "notion": "business", "task": "business",
    "calendar": "business", "workflow": "business", "automate": "business",
    "schedule": "business", "organize": "business", "project management": "business",
    # Finance
    "finance": "finance", "fintech": "finance", "payment": "finance", "invoice": "finance",
    "banking": "finance", "crypto": "crypto", "bitcoin": "crypto", "web3": "crypto",
    "nft": "crypto", "blockchain": "crypto", "defi": "crypto", "wallet": "crypto",
    # Marketing
    "marketing": "business", "seo": "business", "analytics": "business",
    "email": "business", "newsletter": "business", "social media": "business",
    "ads": "business", "landing page": "business", "conversion": "business",
    # Health
    "health": "health", "fitness": "health", "meditation": "health", "sleep": "health",
    "mental health": "health", "wellness": "health", "therapy": "health",
    # Education
    "learn": "education", "course": "education", "education": "education",
    "tutorial": "education", "study": "education", "language": "education",
    # Security
    "security": "security", "privacy": "security", "vpn": "security",
    "password": "security", "encrypt": "security", "auth": "security",
    # Gaming
    "game": "gaming", "gaming": "gaming", "play": "gaming",
}

# Prominent PH hunters/makers
PROMINENT_HUNTERS: Dict[str, float] = {
    "chrismessina": 0.12,
    "rrhoover": 0.12,      # Ryan Hoover (PH founder)
    "kevinaluwi": 0.08,
    "producthunt": 0.10,
    "ben_lang": 0.08,
    "amrith": 0.06,
    "syswarren": 0.06,
    "abadesi": 0.06,
    "hnshah": 0.06,         # Hiten Shah
    "mijustin": 0.06,       # Justin Jackson
    "naval": 0.10,
    "levelsio": 0.10,       # Pieter Levels
    "marckohlbrugge": 0.08,
}


def _detect_category(title: str, summary: str) -> str:
    """Detect category from title + summary keywords."""
    text = f"{title} {summary}".lower()
    matches: Dict[str, int] = {}
    for keyword, category in KEYWORD_CATEGORY_MAP.items():
        if keyword in text:
            klen = len(keyword)
            if category not in matches or klen > matches[category]:
                matches[category] = klen
    if not matches:
        return "tech"
    if len(matches) == 1:
        return next(iter(matches))
    non_tech = {c: l for c, l in matches.items() if c != "tech"}
    if non_tech:
        return max(non_tech, key=non_tech.get)
    return "tech"


def _count_category_matches(title: str, summary: str) -> int:
    """Count how many category keywords match — higher = more confident."""
    text = f"{title} {summary}".lower()
    return sum(1 for kw in KEYWORD_CATEGORY_MAP if kw in text)


def _extract_direct_link(content_html: str) -> Optional[str]:
    """Extract the direct product link from PH content HTML."""
    match = re.search(
        r'<a\s+href="(https://www\.producthunt\.com/r/[^"]+)"', content_html
    )
    if match:
        return match.group(1)
    return None


def _clean_html(html: str) -> str:
    """Strip HTML tags and clean whitespace."""
    text = re.sub(r"<[^>]+>", "", html).strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*Discussion\s*\|\s*Link\s*$", "", text).strip()
    if len(text) > 300:
        text = text[:297] + "..."
    return text


class ProductHuntSource(BaseSource):
    """Fetch trending products from ProductHunt's RSS feed.

    Parameters
    ----------
    limit : int
        Max products to return. Default 50.
    min_quality : float
        Skip products below this quality (0.0 = no filter). Default 0.0.
    category_filter : list of str or None
        Only return products matching these categories. Default None (all).
    """

    name = "producthunt"
    timeout = 15

    def __init__(self, limit: int = 50, min_quality: float = 0.0,
                 category_filter: Optional[List[str]] = None):
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = category_filter

    def _compute_quality(self, position: int, total: int, title: str,
                         summary: str, author: str, category: str) -> float:
        """Compute quality score (0–1) for a PH product."""
        q = 0.0

        # Position rank (0–0.40): PH RSS is ranked by votes, top = best
        if total > 0:
            rank_pct = 1.0 - (position / total)
            q += 0.40 * rank_pct

        # Category keyword confidence (0–0.20)
        kw_matches = _count_category_matches(title, summary)
        q += min(0.20, kw_matches * 0.04)

        # Summary richness (0–0.10): longer descriptions suggest more effort
        summary_len = len(summary)
        if summary_len > 200:
            q += 0.10
        elif summary_len > 100:
            q += 0.07
        elif summary_len > 50:
            q += 0.04

        # Hunter prominence (0–0.12)
        if author:
            q += PROMINENT_HUNTERS.get(author.lower(), 0.0)

        # Base quality floor (all PH products have some curation)
        q += 0.15

        return min(1.0, round(q, 3))

    def crawl(self) -> List[Article]:
        text = self.fetch_url(PRODUCTHUNT_FEED)
        if not text:
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []
        seen_urls: Set[str] = set()
        total = len(feed.entries)

        for position, entry in enumerate(feed.entries[: self.limit]):
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue

            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Extract summary from content
            raw_html = ""
            if hasattr(entry, "content") and entry.content:
                raw_html = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                raw_html = entry.summary or ""

            summary = _clean_html(raw_html)
            direct_link = _extract_direct_link(raw_html)
            author = getattr(entry, "author", "").strip()
            category = _detect_category(title, summary)

            # Quality scoring
            quality = self._compute_quality(position, total, title, summary, author, category)
            if self.min_quality and quality < self.min_quality:
                continue
            if self.category_filter and category not in self.category_filter:
                continue

            timestamp = self._parse_date(entry)

            # Build tags
            tags = ["ph:product"]
            if author:
                tags.append(f"ph:hunter:{author}")
                if author.lower() in PROMINENT_HUNTERS:
                    tags.append("ph:prominent-hunter")
            tags.append(f"ph:category:{category}")
            tags.append(f"ph:quality:{quality:.2f}")

            # Rich summary
            parts = []
            if summary:
                parts.append(summary)
            if author:
                parts.append(f"✍️ Hunter: {author}")
            parts.append(f"📊 Quality: {quality:.2f}")

            articles.append(
                Article(
                    title=title,
                    url=direct_link or link,
                    source="ProductHunt",
                    summary=" | ".join(parts) if parts else "",
                    timestamp=timestamp,
                    category=category,
                    quality_score=quality,
                    discussion_url=link,
                    author=author,
                    tags=tags,
                )
            )

        # Sort by quality descending
        articles.sort(key=lambda a: next(
            (float(t.split(":")[-1]) for t in a.tags if t.startswith("ph:quality:")), 0
        ), reverse=True)

        logger.info(f"[ProductHunt] Parsed {len(articles)} products")
        return articles

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        for field in ("published", "updated"):
            raw = getattr(entry, field, None)
            if raw:
                try:
                    return dateparser.parse(raw)
                except (ValueError, OverflowError):
                    pass
        return None
