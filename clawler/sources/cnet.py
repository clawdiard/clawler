"""CNET source — fetches articles from cnet.com RSS feeds.

Major tech media outlet covering consumer electronics, software, services,
and how technology intersects with daily life. Known for reviews,
buying guides, and consumer-focused tech news.

Enhanced features (v10.83.0):
- Quality scoring (0–1) based on section prominence + keyword specificity + position
- Multi-section support with 6 feed categories
- Two-tier keyword category detection
- Rich summaries with author and section metadata
- Provenance tags: cnet:section, cnet:category, cnet:author
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Cross-section URL deduplication
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

FEEDS = {
    "news": "https://www.cnet.com/rss/news/",
    "reviews": "https://www.cnet.com/rss/reviews/",
    "how-to": "https://www.cnet.com/rss/how-to/",
    "deals": "https://www.cnet.com/rss/deals/",
    "tech": "https://www.cnet.com/rss/tech/",
    "home": "https://www.cnet.com/rss/home/",
}

# Section prominence scores
SECTION_PROMINENCE: Dict[str, float] = {
    "news": 0.55,
    "reviews": 0.50,
    "tech": 0.50,
    "how-to": 0.40,
    "deals": 0.35,
    "home": 0.35,
}

_CATEGORY_KEYWORDS = {
    "ai": [
        "artificial intelligence", "machine learning", "chatgpt", "openai",
        "llm", "generative ai", "copilot", "gemini", "claude", "deep learning",
        "neural network", "gpt-4", "gpt-5",
    ],
    "tech": ["\\bai\\b", "software", "app", "google", "apple", "microsoft", "samsung",
             "android", "iphone", "laptop", "chip", "processor", "robot"],
    "science": ["science", "space", "nasa", "climate", "health", "medical"],
    "security": ["security", "hack", "breach", "privacy", "malware", "vpn",
                 "password", "phishing", "ransomware", "cybersecurity"],
    "business": ["price", "deal", "sale", "buy", "cost", "subscription",
                 "market", "stock", "company", "earnings"],
    "culture": ["streaming", "netflix", "disney", "movie", "show", "game",
                "gaming", "playstation", "xbox", "nintendo"],
}

# Prominent CNET authors (higher quality boost)
PROMINENT_AUTHORS = {
    "dan ackerman", "bridget carey", "scott stein", "lisa eadicicco",
    "ian sherr", "shara tibken", "roger cheng", "sean hollister",
}


def _detect_category(title: str, summary: str, section: str) -> str:
    """Two-tier category detection: specific keywords first, then section fallback."""
    section_map = {"reviews": "tech", "how-to": "tech", "deals": "business", "home": "tech"}
    default = section_map.get(section, "tech")

    text = (title + " " + summary).lower()
    best_cat = None
    best_hits = 0
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        hits = 0
        for kw in keywords:
            if kw.startswith("\\b"):
                if re.search(kw, text):
                    hits += 1
            elif kw in text:
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    if best_cat and best_hits >= 1:
        return best_cat
    return default


def _compute_quality(section: str, category: str, section_default: str,
                     position: int, author: str) -> float:
    """Quality score (0–1) based on section prominence + position + specificity + author."""
    base = SECTION_PROMINENCE.get(section, 0.40)
    # Position decay
    position_factor = 1.0 / (1.0 + 0.05 * position)
    score = base * position_factor
    # Boost for specific keyword-detected category
    if category != section_default:
        score = min(1.0, score + 0.08)
    # Boost for prominent authors
    if author.lower() in PROMINENT_AUTHORS:
        score = min(1.0, score + 0.10)
    return round(min(1.0, score), 3)


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


class CNETSource(BaseSource):
    """Fetch articles from CNET's RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. Default: ["news", "reviews"].
    limit : int
        Max articles per feed. Default 30.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    exclude_sections : list of str or None
        Exclude these sections.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "cnet"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        limit: int = 30,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.sections = sections or ["news", "reviews"]
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen: Set[str] = set()

        active_sections = [s for s in self.sections if s not in (self.exclude_sections or [])]

        for section in active_sections:
            feed_url = FEEDS.get(section)
            if not feed_url:
                continue
            try:
                xml_text = self.fetch_url(feed_url)
                if xml_text:
                    section_articles = self._parse_feed(xml_text, section, seen)
                    articles.extend(section_articles)
                    logger.info(f"[CNET] {section}: {len(section_articles)} articles")
            except Exception as e:
                logger.warning(f"[CNET] Failed to fetch {section}: {e}")

        # Apply filters
        if self.min_quality > 0:
            articles = [a for a in articles if (a.quality_score or 0) >= self.min_quality]

        if self.category_filter:
            articles = [a for a in articles if a.category in self.category_filter]

        # Sort by quality descending
        articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Global limit
        if self.global_limit:
            articles = articles[:self.global_limit]

        logger.info(f"[CNET] Total: {len(articles)} articles")
        return articles[:self.limit] if not self.global_limit else articles

    def _parse_feed(self, xml_text: str, section: str, seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[CNET] XML parse error for {section}: {e}")
            return articles

        channel = root.find("channel")
        if channel is None:
            return articles

        section_map = {"reviews": "tech", "how-to": "tech", "deals": "business", "home": "tech"}
        section_default = section_map.get(section, "tech")

        for position, item in enumerate(channel.findall("item")):
            try:
                article = self._parse_item(item, section, section_default, position, seen)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[CNET] Skipping item in {section}: {e}")

        return articles

    def _parse_item(self, item, section: str, section_default: str,
                    position: int, seen: Set[str]) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Summary
        summary = ""
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Author
        author = ""
        for ns_prefix in ["{http://purl.org/dc/elements/1.1/}", ""]:
            author_el = item.find(f"{ns_prefix}creator")
            if author_el is not None and author_el.text:
                author = author_el.text.strip()
                break
        if not author:
            author_el = item.find("author")
            if author_el is not None and author_el.text:
                author = author_el.text.strip()

        # Timestamp
        ts = None
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            ts = _parse_date(pub_el.text)

        # Category detection
        category = _detect_category(title, summary, section)

        # Quality scoring
        quality = _compute_quality(section, category, section_default, position, author)

        # Build rich summary
        parts = []
        if author:
            parts.append(f"✍️ {author}")
        parts.append(f"📰 {section.title()}")
        if summary:
            parts.append(summary)
        rich_summary = " · ".join(parts[:2])
        if summary:
            rich_summary += f" — {summary}"

        # Provenance tags
        tags = [f"cnet:section:{section}", f"cnet:category:{category}"]
        if author:
            tags.append(f"cnet:author:{author.lower()}")
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"cnet:tag:{cat_el.text.strip().lower()}")

        return Article(
            title=title,
            url=url,
            source=f"CNET ({section.title()})",
            summary=rich_summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=quality,
        )
