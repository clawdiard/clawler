"""ProductHunt source — trending products via RSS (no key needed).

Enhanced with:
- Author/hunter extraction
- Direct product link extraction from content HTML
- Keyword-based category detection from title + summary
- Configurable limit
- Rich tags (author, category keywords)
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


def _detect_category(title: str, summary: str) -> str:
    """Detect category from title + summary keywords.

    Collects all matching categories and returns the most specific one
    (non-tech preferred over tech default).
    """
    text = f"{title} {summary}".lower()
    matches: Dict[str, int] = {}  # category → max keyword length
    for keyword, category in KEYWORD_CATEGORY_MAP.items():
        if keyword in text:
            klen = len(keyword)
            if category not in matches or klen > matches[category]:
                matches[category] = klen
    if not matches:
        return "tech"
    # Prefer non-"tech" categories (more specific), break ties by keyword length
    if len(matches) == 1:
        return next(iter(matches))
    non_tech = {c: l for c, l in matches.items() if c != "tech"}
    if non_tech:
        return max(non_tech, key=non_tech.get)
    return "tech"


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
    # Remove "Discussion | Link" boilerplate
    text = re.sub(r"\s*Discussion\s*\|\s*Link\s*$", "", text).strip()
    if len(text) > 300:
        text = text[:297] + "..."
    return text


class ProductHuntSource(BaseSource):
    """Fetch trending products from ProductHunt's RSS feed."""

    name = "producthunt"
    timeout = 15

    def __init__(self, limit: int = 50):
        """
        Args:
            limit: Max products to return.
        """
        self.limit = limit

    def crawl(self) -> List[Article]:
        text = self.fetch_url(PRODUCTHUNT_FEED)
        if not text:
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []
        seen_urls: Set[str] = set()

        for entry in feed.entries[: self.limit]:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue

            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Extract summary from content (prefer content over summary)
            raw_html = ""
            if hasattr(entry, "content") and entry.content:
                raw_html = entry.content[0].get("value", "")
            elif hasattr(entry, "summary"):
                raw_html = entry.summary or ""

            summary = _clean_html(raw_html)

            # Extract direct product link
            direct_link = _extract_direct_link(raw_html)

            # Author (hunter)
            author = getattr(entry, "author", "").strip()

            # Category detection
            category = _detect_category(title, summary)

            # Timestamp
            timestamp = self._parse_date(entry)

            # Build tags
            tags = ["ph:product"]
            if author:
                tags.append(f"ph:hunter:{author}")
            tags.append(f"ph:category:{category}")

            # Rich summary with hunter info
            parts = []
            if summary:
                parts.append(summary)
            if author:
                parts.append(f"Hunter: {author}")

            articles.append(
                Article(
                    title=title,
                    url=direct_link or link,
                    source="ProductHunt",
                    summary=" | ".join(parts) if parts else "",
                    timestamp=timestamp,
                    category=category,
                    discussion_url=link,
                    author=author,
                    tags=tags,
                )
            )

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
