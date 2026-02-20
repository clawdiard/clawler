"""TechCrunch source — fetches articles from TechCrunch RSS feeds.

TechCrunch is the leading startup and venture capital news publication,
covering fundraising, product launches, AI, and the tech industry.

Enhanced features:
- 8 section feeds (main, startups, venture, apps, AI, security, crypto, hardware)
- Two-tier keyword category detection (regex-based specific categories before section fallback)
- Quality scoring (0–1) based on section prominence, position, keyword specificity, and author reputation
- Prominent author recognition (senior reporters and editors)
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with ✍️ author and 📰 section
- Provenance tags: tc:section, tc:category, tc:author, tc:tag
- Cross-section URL deduplication
- Quality-sorted output
"""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# TechCrunch RSS feeds
TC_FEEDS: Dict[str, str] = {
    "main": "https://techcrunch.com/feed/",
    "startups": "https://techcrunch.com/category/startups/feed/",
    "venture": "https://techcrunch.com/category/venture/feed/",
    "apps": "https://techcrunch.com/category/apps/feed/",
    "ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "security": "https://techcrunch.com/category/security/feed/",
    "crypto": "https://techcrunch.com/category/cryptocurrency/feed/",
    "hardware": "https://techcrunch.com/category/hardware/feed/",
}

# Section → default Clawler category mapping
_SECTION_CATEGORY: Dict[str, str] = {
    "main": "tech",
    "startups": "business",
    "venture": "business",
    "apps": "tech",
    "ai": "ai",
    "security": "security",
    "crypto": "crypto",
    "hardware": "tech",
}

# Section prominence scores
SECTION_PROMINENCE: Dict[str, float] = {
    "main": 0.55,
    "ai": 0.55,
    "startups": 0.50,
    "venture": 0.50,
    "security": 0.50,
    "apps": 0.45,
    "crypto": 0.40,
    "hardware": 0.45,
}

# Prominent TechCrunch authors
PROMINENT_AUTHORS: Dict[str, float] = {
    "sarah perez": 0.08,
    "manish singh": 0.08,
    "natasha lomas": 0.08,
    "devin coldewey": 0.08,
    "mike butcher": 0.10,
    "frederic lardinois": 0.10,
    "alex wilhelm": 0.10,
    "ingrid lunden": 0.08,
    "brian heater": 0.08,
    "kyle wiggers": 0.10,
    "connie loizos": 0.08,
    "zack whittaker": 0.12,
    "haje jan kamps": 0.06,
    "ivan mehta": 0.06,
    "paul sawers": 0.08,
    "aisha malik": 0.06,
    "maxwell zeff": 0.06,
}

# Keyword rules for finer category detection
_CATEGORY_RULES = [
    ("ai", re.compile(r"\b(ai|llm|gpt|openai|anthropic|claude|gemini|machine.?learn|neural|deep.?learn|transformer|diffusion|midjourney|stable.?diffusion)\b", re.I)),
    ("security", re.compile(r"\b(security|vulnerabilit|exploit|cve|ransomware|malware|breach|zero.?day|hack(?:ed|ing)|spyware|phishing)\b", re.I)),
    ("crypto", re.compile(r"\b(bitcoin|ethereum|crypto|blockchain|web3|defi|nft|stablecoin)\b", re.I)),
    ("business", re.compile(r"\b(startup|funding|ipo|acquisition|layoff|revenue|valuation|series.[a-d]|raises?\s+\$|unicorn|seed.?round)\b", re.I)),
    ("science", re.compile(r"\b(nasa|spacex|climate|quantum|biotech|crispr|genome|research.?paper)\b", re.I)),
    ("health", re.compile(r"\b(healthtech|telehealth|fda|pharmaceutical|clinical.?trial|digital.?health)\b", re.I)),
]


def _detect_category(title: str, summary: str, section: str) -> str:
    """Detect category from title/summary keywords, falling back to section mapping."""
    if section != "main":
        return _SECTION_CATEGORY.get(section, "tech")
    text = f"{title} {summary}"
    for cat, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return cat
    return "tech"


def _compute_quality(
    section: str,
    category: str,
    section_category: str,
    position: int,
    author: str,
) -> float:
    """Quality score (0–1) based on section prominence, position, keyword specificity, and author."""
    base = SECTION_PROMINENCE.get(section, 0.40)
    position_factor = 1.0 / (1.0 + 0.05 * position)
    score = base * position_factor
    # Boost for keyword-detected category
    if category != section_category:
        score = min(1.0, score + 0.08)
    # Author reputation boost
    author_boost = PROMINENT_AUTHORS.get(author.lower(), 0.0)
    score = min(1.0, score + author_boost)
    return round(min(1.0, score), 3)


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse RFC 2822 date from RSS pubDate."""
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class TechCrunchSource(BaseSource):
    """Fetch articles from TechCrunch RSS feeds.

    Parameters
    ----------
    feeds : list of str or None
        Section feeds to crawl. Default: ["main"].
    limit : int
        Max articles per feed. Default 25.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    exclude_sections : list of str or None
        Exclude these sections.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "techcrunch"

    def __init__(
        self,
        feeds: Optional[List[str]] = None,
        limit: int = 25,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.tc_feeds = feeds or ["main"]
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        active_feeds = self.tc_feeds
        if self.exclude_sections:
            active_feeds = [f for f in active_feeds if f not in self.exclude_sections]

        for section in active_feeds:
            feed_url = TC_FEEDS.get(section)
            if not feed_url:
                logger.warning(f"[TechCrunch] Unknown feed: {section}")
                continue
            try:
                xml_text = self.fetch_url(feed_url)
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, section, seen_urls)
                all_articles.extend(parsed)
                logger.info(f"[TechCrunch] {section}: {len(parsed)} articles")
            except Exception as e:
                logger.warning(f"[TechCrunch] Failed to fetch {section}: {e}")

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

        logger.info(f"[TechCrunch] Total: {len(all_articles)} articles from {len(active_feeds)} feed(s)")
        return all_articles

    def _parse_feed(self, xml_text: str, section: str, seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[TechCrunch] XML parse error for {section}: {e}")
            return articles

        ns = {"dc": "http://purl.org/dc/elements/1.1/", "content": "http://purl.org/rss/1.0/modules/content/"}

        for position, item in enumerate(root.findall(".//item")[:self.limit]):
            try:
                article = self._parse_item(item, section, position, seen, ns)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[TechCrunch] Skipping item in {section}: {e}")

        return articles

    def _parse_item(self, item, section: str, position: int, seen: Set[str], ns: dict) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pubdate_el = item.find("pubDate")
        creator_el = item.find("dc:creator", ns)

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        summary = ""
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
            if len(summary) > 300:
                summary = summary[:297] + "..."

        author = (creator_el.text or "").strip() if creator_el is not None else ""
        ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)

        section_category = _SECTION_CATEGORY.get(section, "tech")
        category = _detect_category(title, summary, section)
        quality = _compute_quality(section, category, section_category, position, author)

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
            f"tc:section:{section}",
            f"tc:category:{category}",
        ]
        if author:
            tags.append(f"tc:author:{author.lower()}")
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"tc:tag:{cat_el.text.strip().lower()}")

        return Article(
            title=title,
            url=url,
            source=f"TechCrunch ({section})",
            summary=rich_summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=quality,
        )
