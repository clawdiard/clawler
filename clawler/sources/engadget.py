"""Engadget source — fetches articles from Engadget RSS feed.

Consumer tech, gadgets, gaming, and entertainment coverage.
"""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

ENGADGET_FEED = "https://www.engadget.com/rss.xml"

# Keyword-based category detection
_CATEGORY_RULES = [
    ("ai", re.compile(r"\b(ai|llm|gpt|openai|anthropic|machine.?learn|chatbot|copilot)\b", re.I)),
    ("gaming", re.compile(r"\b(game|gaming|playstation|xbox|nintendo|steam|console|esport)\b", re.I)),
    ("science", re.compile(r"\b(nasa|space|climate|research|study|satellite|mars|moon)\b", re.I)),
    ("security", re.compile(r"\b(security|hack|breach|malware|ransomware|privacy|surveillance)\b", re.I)),
    ("automotive", re.compile(r"\b(ev|electric.?vehicle|tesla|rivian|self.?driving|autonomous)\b", re.I)),
    ("entertainment", re.compile(r"\b(stream|netflix|disney|movie|film|tv|show|music|spotify|apple.?tv)\b", re.I)),
]


def _detect_category(title: str, summary: str) -> str:
    text = f"{title} {summary}"
    for cat, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return cat
    return "tech"


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class EngadgetSource(BaseSource):
    """Fetch articles from Engadget RSS feed.

    Parameters
    ----------
    limit : int
        Max articles to return. Default 25.
    """

    name = "engadget"

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        xml_text = self.fetch_url(ENGADGET_FEED)
        if not xml_text:
            logger.warning("[Engadget] Empty response from feed")
            return []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[Engadget] XML parse error: {e}")
            return []

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        seen: Set[str] = set()
        articles: List[Article] = []

        for item in root.findall(".//item")[:self.limit]:
            try:
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                pubdate_el = item.find("pubDate")
                creator_el = item.find("dc:creator", ns)

                title = (title_el.text or "").strip() if title_el is not None else ""
                url = (link_el.text or "").strip() if link_el is not None else ""

                if not title or not url or url in seen:
                    continue
                seen.add(url)

                summary = ""
                if desc_el is not None and desc_el.text:
                    summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
                    if len(summary) > 300:
                        summary = summary[:297] + "..."

                author = (creator_el.text or "").strip() if creator_el is not None else ""
                ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)
                category = _detect_category(title, summary)

                tags = []
                for cat_el in item.findall("category"):
                    if cat_el.text:
                        tags.append(f"engadget:{cat_el.text.strip().lower()}")

                articles.append(Article(
                    title=title,
                    url=url,
                    source="Engadget",
                    summary=summary,
                    timestamp=ts,
                    category=category,
                    tags=tags,
                    author=author,
                ))
            except Exception as e:
                logger.debug(f"[Engadget] Skipping item: {e}")

        logger.info(f"[Engadget] Fetched {len(articles)} articles")
        return articles
