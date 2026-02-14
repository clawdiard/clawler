"""Slashdot source — scrapes the Slashdot RSS feed for tech news and discussion."""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

SLASHDOT_RSS = "https://rss.slashdot.org/Slashdot/slashdotMain"


class SlashdotSource(BaseSource):
    """Fetch stories from Slashdot via their public RSS feed."""

    name = "slashdot"

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        try:
            import feedparser
        except ImportError:
            logger.warning("[Slashdot] feedparser not installed, skipping")
            return []

        try:
            text = self.fetch_url(SLASHDOT_RSS)
            if not text:
                return []
        except Exception as e:
            logger.warning(f"[Slashdot] Failed to fetch RSS: {e}")
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []

        for entry in feed.entries[: self.limit]:
            try:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if not title or not url:
                    continue

                # Parse summary (strip HTML tags for clean text)
                summary_raw = entry.get("summary", "")
                summary = _strip_html(summary_raw)[:300]

                # Parse author (Slashdot uses dc:creator or author)
                author = entry.get("author", "") or entry.get("dc_creator", "")

                # Parse timestamp
                ts = None
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    try:
                        from calendar import timegm
                        ts = datetime.fromtimestamp(timegm(published), tz=timezone.utc)
                    except Exception:
                        pass

                # Slashdot tags/departments
                tags = []
                for tag in entry.get("tags", []):
                    term = tag.get("term", "")
                    if term:
                        tags.append(f"slashdot:{term}")

                # Slashdot department (fun editorial label)
                department = entry.get("slash_department", "")
                if department:
                    summary = f"Dept: {department} — {summary}" if summary else f"Dept: {department}"

                # Comments URL is typically the link itself on Slashdot
                comments_url = entry.get("comments", url)

                category = _map_category(tags, title)

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source="Slashdot",
                        summary=summary,
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=author,
                        discussion_url=comments_url if comments_url != url else "",
                    )
                )
            except Exception as e:
                logger.debug(f"[Slashdot] Skipping entry: {e}")
                continue

        logger.info(f"[Slashdot] Fetched {len(articles)} stories")
        return articles


def _strip_html(text: str) -> str:
    """Minimal HTML tag stripper."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _map_category(tags: List[str], title: str) -> str:
    """Map Slashdot tags/title to Clawler categories."""
    combined = " ".join(tags).lower() + " " + title.lower()
    if any(kw in combined for kw in ("security", "privacy", "hack", "breach", "vulnerability")):
        return "security"
    if any(kw in combined for kw in ("science", "space", "physics", "climate", "nasa")):
        return "science"
    if any(kw in combined for kw in ("business", "economy", "startup", "acquisition", "ipo")):
        return "business"
    if any(kw in combined for kw in ("politics", "government", "law", "court")):
        return "world"
    if any(kw in combined for kw in ("games", "entertainment", "movie", "book")):
        return "culture"
    return "tech"
