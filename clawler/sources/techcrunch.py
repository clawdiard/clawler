"""TechCrunch source — fetches articles from TechCrunch RSS feeds.

Supports main feed plus category feeds (startups, AI, venture, apps, etc.)
with keyword-based category detection and quality scoring.
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

# Section → Clawler category mapping
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

# Keyword rules for finer category detection on main feed articles
_CATEGORY_RULES = [
    ("ai", re.compile(r"\b(ai|llm|gpt|openai|anthropic|claude|gemini|machine.?learn|neural|deep.?learn|transformer)\b", re.I)),
    ("security", re.compile(r"\b(security|vulnerabilit|exploit|cve|ransomware|malware|breach|zero.?day|hack(?:ed|ing))\b", re.I)),
    ("crypto", re.compile(r"\b(bitcoin|ethereum|crypto|blockchain|web3|defi|nft)\b", re.I)),
    ("business", re.compile(r"\b(startup|funding|ipo|acquisition|layoff|revenue|valuation|series.[a-d]|raises?\s+\$)\b", re.I)),
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
    feeds : list of str
        Section feeds to crawl. Default: ["main"].
    limit : int
        Max articles per feed. Default 25.
    """

    name = "techcrunch"

    def __init__(self, feeds: Optional[List[str]] = None, limit: int = 25):
        self.tc_feeds = feeds or ["main"]
        self.limit = limit

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        for section in self.tc_feeds:
            feed_url = TC_FEEDS.get(section)
            if not feed_url:
                logger.warning(f"[TechCrunch] Unknown feed: {section}")
                continue
            try:
                xml_text = self.fetch_url(feed_url)
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, section, seen_urls)
                articles.extend(parsed)
            except Exception as e:
                logger.warning(f"[TechCrunch] Failed to fetch {section}: {e}")

        logger.info(f"[TechCrunch] Fetched {len(articles)} articles from {len(self.tc_feeds)} feed(s)")
        return articles

    def _parse_feed(self, xml_text: str, section: str, seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[TechCrunch] XML parse error for {section}: {e}")
            return articles

        ns = {"dc": "http://purl.org/dc/elements/1.1/", "content": "http://purl.org/rss/1.0/modules/content/"}

        for item in root.findall(".//item")[:self.limit]:
            try:
                article = self._parse_item(item, section, seen, ns)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[TechCrunch] Skipping item in {section}: {e}")

        return articles

    def _parse_item(self, item, section: str, seen: Set[str], ns: dict) -> Optional[Article]:
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
        category = _detect_category(title, summary, section)

        # Collect RSS category tags
        tags = [f"tc-section:{section}"]
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"tc:{cat_el.text.strip().lower()}")

        return Article(
            title=title,
            url=url,
            source=f"TechCrunch",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
        )
