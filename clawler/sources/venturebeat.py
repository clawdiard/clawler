"""VentureBeat source — AI, gaming, and enterprise tech news.

VentureBeat is a leading tech publication focused on transformative technology,
particularly AI/ML, gaming, and enterprise innovation.

Enhanced with:
- Quality scoring based on author prominence, content signals, and category specificity
- Keyword-based category detection with multi-signal matching
- Prominent author tracking
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

VENTUREBEAT_FEED = "https://venturebeat.com/feed/"

# Keyword sets for category detection
_AI_KEYWORDS = {"ai", "artificial intelligence", "machine learning", "llm", "generative ai",
                "chatgpt", "openai", "anthropic", "deepmind", "neural", "transformer", "gpt"}
_SECURITY_KEYWORDS = {"security", "cyber", "hack", "breach", "ransomware", "vulnerability",
                      "malware", "phishing", "zero-day"}
_GAMING_KEYWORDS = {"game", "gaming", "esports", "xbox", "playstation", "nintendo", "steam",
                    "unity", "unreal"}
_ENTERPRISE_KEYWORDS = {"enterprise", "saas", "cloud", "startup", "funding", "vc",
                        "acquisition", "ipo", "series a", "series b"}

# Prominent VentureBeat authors
_PROMINENT_AUTHORS = {
    "dean takahashi", "jeff grubb", "emil protalinski", "carl franzen",
    "michael nuñez", "sharon goldman", "taryn plumb", "sean michael kerner",
    "khari johnson", "kyle wiggers",
}


class VentureBeatSource(BaseSource):
    """Fetch articles from VentureBeat's RSS feed."""

    name = "venturebeat"

    def __init__(self, limit: int = 30, **kwargs):
        super().__init__(**kwargs)
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        try:
            xml_text = self.fetch_url(VENTUREBEAT_FEED)
            if not xml_text:
                return articles
            articles = self._parse_feed(xml_text)
        except Exception as e:
            logger.warning(f"[VentureBeat] Failed to fetch feed: {e}")
        logger.info(f"[VentureBeat] Fetched {len(articles)} articles")
        return articles

    def _parse_feed(self, xml_text: str) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[VentureBeat] XML parse error: {e}")
            return articles

        seen: Set[str] = set()
        items = root.findall(".//item")

        for item in items[:self.limit]:
            try:
                article = self._parse_item(item, seen)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[VentureBeat] Skipping item: {e}")

        return articles

    def _parse_item(self, item, seen: Set[str]) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Description
        summary = ""
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Author (dc:creator)
        author = ""
        ns_dc = {"dc": "http://purl.org/dc/elements/1.1/"}
        creator_el = item.find("dc:creator", ns_dc)
        if creator_el is not None and creator_el.text:
            author = creator_el.text.strip()

        # Timestamp
        ts = None
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            ts = _parse_date(pub_el.text)

        # Categories / tags
        tags = []
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"vb:{cat_el.text.strip().lower()}")

        category = _detect_category(title, summary, tags)
        quality = _compute_quality(title, summary, author, category)

        return Article(
            title=title,
            url=url,
            source="VentureBeat",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=quality,
        )


def _detect_category(title: str, summary: str, tags: List[str]) -> str:
    """Heuristic category detection from title, summary, and tags."""
    text = (title + " " + summary + " " + " ".join(tags)).lower()
    if any(kw in text for kw in _AI_KEYWORDS):
        return "ai"
    if any(kw in text for kw in _SECURITY_KEYWORDS):
        return "security"
    if any(kw in text for kw in _GAMING_KEYWORDS):
        return "gaming"
    if any(kw in text for kw in _ENTERPRISE_KEYWORDS):
        return "business"
    return "tech"


def _compute_quality(title: str, summary: str, author: str, category: str) -> float:
    """Compute quality score (0.0–1.0) based on content signals."""
    score = 0.5

    # Prominent author boost
    if author.lower() in _PROMINENT_AUTHORS:
        score += 0.15

    # Specific category (non-generic) boost
    if category != "tech":
        score += 0.05

    # Title quality
    title_words = len(title.split())
    if title_words >= 6:
        score += 0.05
    if title_words >= 10:
        score += 0.05

    # Summary richness
    if len(summary) > 100:
        score += 0.05
    if len(summary) > 200:
        score += 0.05

    # AI content bonus (VB's forte)
    if category == "ai":
        score += 0.05

    return min(score, 1.0)


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None
