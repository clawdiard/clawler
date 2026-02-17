"""Hacker Noon source — tech articles via public RSS feed."""
import logging
import re
from datetime import datetime, timezone
from typing import List
from xml.etree import ElementTree as ET
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

HACKERNOON_FEED = "https://hackernoon.com/feed"


class HackerNoonSource(BaseSource):
    """Fetch latest articles from Hacker Noon RSS feed."""

    name = "hackernoon"

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        text = self.fetch_url(HACKERNOON_FEED)
        if not text:
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            logger.warning(f"[HackerNoon] XML parse error: {e}")
            return []

        articles: List[Article] = []
        ns = {"dc": "http://purl.org/dc/elements/1.1/",
              "content": "http://purl.org/rss/1.0/modules/content/"}

        items = root.findall(".//item")
        for item in items[: self.limit]:
            try:
                title = (item.findtext("title") or "").strip()
                url = (item.findtext("link") or "").strip()
                if not title or not url:
                    continue

                description = (item.findtext("description") or "").strip()
                # Strip HTML tags from description for clean summary
                summary = re.sub(r"<[^>]+>", "", description)[:300]

                author = (item.findtext("dc:creator", namespaces=ns) or "").strip()

                # Parse categories/tags
                tags = []
                for cat in item.findall("category"):
                    if cat.text:
                        tags.append(cat.text.strip().lower())

                # Parse pub date
                ts = None
                pub_date = item.findtext("pubDate")
                if pub_date:
                    try:
                        from email.utils import parsedate_to_datetime
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                category = _map_category(tags)

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source="Hacker Noon",
                        summary=summary,
                        timestamp=ts,
                        category=category,
                        tags=[f"hackernoon:{t}" for t in tags[:5]],
                        author=author,
                    )
                )
            except Exception as e:
                logger.debug(f"[HackerNoon] Skipping item: {e}")
                continue

        logger.info(f"[HackerNoon] Fetched {len(articles)} articles")
        return articles


def _map_category(tags: List[str]) -> str:
    """Map Hacker Noon tags to Clawler categories."""
    tag_set = set(t.lower() for t in tags)
    if tag_set & {"ai", "artificial-intelligence", "machine-learning", "chatgpt", "llm"}:
        return "ai"
    if tag_set & {"security", "cybersecurity", "privacy", "hacking"}:
        return "security"
    if tag_set & {"startup", "business", "marketing", "entrepreneurship", "venture-capital"}:
        return "business"
    if tag_set & {"blockchain", "crypto", "web3", "bitcoin", "ethereum", "defi"}:
        return "crypto"
    if tag_set & {"science", "space", "climate"}:
        return "science"
    if tag_set & {"gaming", "game-development"}:
        return "gaming"
    return "tech"
