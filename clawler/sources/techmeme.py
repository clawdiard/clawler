"""TechMeme source — curated tech news river via RSS (no key needed).

Enhanced with keyword-based category detection, quality scoring from
source_weights.yaml, and discussion link extraction.
"""
import logging
import re
from datetime import datetime
from typing import List, Optional
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

TECHMEME_FEED = "https://www.techmeme.com/feed.xml"

# Keyword → category mapping (checked against lowered title + summary)
_CATEGORY_KEYWORDS = {
    "security": ["hack", "breach", "vulnerability", "ransomware", "malware",
                  "cyberattack", "phishing", "zero-day", "cve-", "exploit",
                  "encryption", "cybersecurity", "infosec"],
    "science": ["research", "study finds", "scientists", "nasa", "space",
                "climate", "quantum", "physics", "biology", "genome",
                "crispr", "telescope", "mars", "asteroid"],
    "business": ["acquisition", "ipo", "valuation", "funding", "layoff",
                 "revenue", "earnings", "merger", "antitrust", "ftc",
                 "sec ", "stock", "investor", "startup raises"],
    "world": ["ukraine", "china", "eu ", "european union", "nato",
              "sanctions", "geopolit", "diplomat", "united nations"],
    "culture": ["streaming", "netflix", "spotify", "gaming", "game",
                "movie", "film", "music", "entertainment", "creator"],
}


def _detect_category(title: str, summary: str) -> str:
    """Detect article category from title and summary keywords."""
    text = f"{title} {summary}".lower()
    scores = {}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "tech"  # TechMeme default


class TechMemeSource(BaseSource):
    """Fetch top tech stories from TechMeme's RSS feed.

    Features:
    - Keyword-based category detection (security, science, business, world, culture, tech)
    - Per-article quality scoring using source_weights.yaml
    - Discussion link extraction from TechMeme river pages
    - Author extraction from feed metadata
    """

    name = "techmeme"
    timeout = 15

    def crawl(self) -> List[Article]:
        text = self.fetch_url(TECHMEME_FEED)
        if not text:
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []

        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue

            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary.strip()
                # Strip HTML tags from summary
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            timestamp = self._parse_date(entry)
            author = self._extract_author(entry)
            category = _detect_category(title, summary)

            # TechMeme entry IDs are often the discussion page URL
            discussion_url = ""
            entry_id = getattr(entry, "id", "")
            if entry_id and "techmeme.com" in entry_id and entry_id != link:
                discussion_url = entry_id

            # Build tags from category keywords that matched
            tags = self._extract_tags(title, summary)

            article = Article(
                title=title,
                url=link,
                source="TechMeme",
                summary=summary,
                timestamp=timestamp,
                category=category,
                author=author,
                discussion_url=discussion_url,
                tags=tags,
            )

            # Apply quality score from weights (TechMeme curates from known
            # publications, so individual articles inherit TechMeme's base score)
            try:
                from clawler.weights import get_quality_score
                article.quality_score = get_quality_score("TechMeme")
            except Exception:
                article.quality_score = 0.79  # fallback

            articles.append(article)

        logger.info(f"[TechMeme] Parsed {len(articles)} articles across categories: "
                     f"{', '.join(sorted(set(a.category for a in articles)))}")
        return articles

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """Extract and parse date from feed entry."""
        for field in ("published", "updated"):
            raw = getattr(entry, field, None)
            if raw:
                try:
                    return dateparser.parse(raw)
                except (ValueError, OverflowError):
                    pass
        return None

    @staticmethod
    def _extract_author(entry) -> str:
        """Extract author from feed entry metadata."""
        # feedparser normalizes author fields
        author = getattr(entry, "author", "")
        if not author:
            author_detail = getattr(entry, "author_detail", None)
            if author_detail:
                author = getattr(author_detail, "name", "")
        return author.strip() if author else ""

    @staticmethod
    def _extract_tags(title: str, summary: str) -> List[str]:
        """Extract relevant tags from title and summary."""
        text = f"{title} {summary}".lower()
        tags = []
        tag_keywords = {
            "ai": ["artificial intelligence", " ai ", "machine learning", "llm",
                    "gpt", "chatgpt", "openai", "anthropic", "gemini", "claude"],
            "crypto": ["bitcoin", "crypto", "blockchain", "ethereum", "web3"],
            "cloud": ["aws", "azure", "google cloud", "gcp", "cloud computing"],
            "apple": ["apple", "iphone", "ipad", "macos", "wwdc"],
            "google": ["google", "alphabet", "android", "chrome"],
            "meta": ["meta", "facebook", "instagram", "whatsapp", "threads"],
            "microsoft": ["microsoft", "windows", "copilot", "github"],
            "regulation": ["regulation", "antitrust", "gdpr", "privacy law"],
            "open-source": ["open source", "open-source", "foss", "linux"],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        return tags
