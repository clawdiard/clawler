"""The Verge source — fetches articles from theverge.com RSS feed.

Major tech news publication covering gadgets, science, entertainment,
and the intersection of technology and culture.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

VERGE_FEED = "https://www.theverge.com/rss/index.xml"


class TheVergeSource(BaseSource):
    """Fetch articles from The Verge's RSS feed."""

    name = "theverge"

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        try:
            xml_text = self.fetch_url(VERGE_FEED)
            if not xml_text:
                return articles
            articles = self._parse_feed(xml_text)
        except Exception as e:
            logger.warning(f"[TheVerge] Failed to fetch feed: {e}")
        logger.info(f"[TheVerge] Fetched {len(articles)} articles")
        return articles

    def _parse_feed(self, xml_text: str) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[TheVerge] XML parse error: {e}")
            return articles

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        seen: Set[str] = set()

        # The Verge uses Atom format
        entries = root.findall("atom:entry", ns)
        if not entries:
            # Fallback to RSS 2.0
            entries = root.findall(".//item")

        for entry in entries[:self.limit]:
            try:
                article = self._parse_entry(entry, seen, ns)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[TheVerge] Skipping entry: {e}")

        return articles

    def _parse_entry(self, entry, seen: Set[str], ns: dict) -> Optional[Article]:
        # Atom format
        title_el = entry.find("atom:title", ns)
        if title_el is None:
            title_el = entry.find("title")

        link_el = entry.find("atom:link[@rel='alternate']", ns)
        if link_el is not None:
            url = link_el.get("href", "").strip()
        else:
            link_el = entry.find("link")
            url = (link_el.text or "").strip() if link_el is not None else ""

        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Summary / content
        summary = ""
        for tag in ["atom:summary", "atom:content"]:
            el = entry.find(tag, ns)
            if el is not None and el.text:
                summary = re.sub(r"<[^>]+>", "", el.text).strip()
                break
        if not summary:
            desc_el = entry.find("description")
            if desc_el is not None and desc_el.text:
                summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Author
        author = ""
        author_el = entry.find("atom:author/atom:name", ns)
        if author_el is not None and author_el.text:
            author = author_el.text.strip()

        # Timestamp
        ts = None
        for tag in ["atom:published", "atom:updated", "pubDate"]:
            ts_el = entry.find(tag, ns) if "atom:" in tag else entry.find(tag)
            if ts_el is not None and ts_el.text:
                ts = _parse_date(ts_el.text)
                if ts:
                    break

        # Categories / tags
        tags = []
        for cat_el in entry.findall("atom:category", ns):
            term = cat_el.get("term", "")
            if term:
                tags.append(f"verge:{term.strip().lower()}")
        for cat_el in entry.findall("category"):
            if cat_el.text:
                tags.append(f"verge:{cat_el.text.strip().lower()}")

        # Categorize based on tags/title
        category = _detect_category(title, tags)

        return Article(
            title=title,
            url=url,
            source="The Verge",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
        )


def _detect_category(title: str, tags: List[str]) -> str:
    """Heuristic category detection from title and tags."""
    text = title.lower() + " " + " ".join(tags)
    if any(w in text for w in ["ai", "artificial intelligence", "machine learning", "chatgpt", "openai"]):
        return "ai"
    if any(w in text for w in ["security", "hack", "breach", "privacy", "surveillance"]):
        return "security"
    if any(w in text for w in ["science", "space", "nasa", "climate", "research"]):
        return "science"
    if any(w in text for w in ["game", "gaming", "playstation", "xbox", "nintendo"]):
        return "gaming"
    if any(w in text for w in ["movie", "film", "tv", "streaming", "netflix", "disney"]):
        return "culture"
    return "tech"


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    # ISO 8601
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        pass
    # RFC 2822
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
