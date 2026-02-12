"""RSS/Atom feed source — the workhorse of Clawler."""
import logging
from datetime import datetime
from typing import List, Optional
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

# Curated list of high-quality RSS feeds
DEFAULT_FEEDS = [
    # --- Tech ---
    {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica", "category": "tech"},
    {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge", "category": "tech"},
    {"url": "https://techcrunch.com/feed/", "source": "TechCrunch", "category": "tech"},
    {"url": "https://www.wired.com/feed/rss", "source": "Wired", "category": "tech"},
    {"url": "https://feeds.feedburner.com/TechCrunch/", "source": "TechCrunch (FB)", "category": "tech"},
    # --- World News ---
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "source": "NY Times", "category": "world"},
    {"url": "https://feeds.bbci.co.uk/news/rss.xml", "source": "BBC News", "category": "world"},
    {"url": "https://www.theguardian.com/world/rss", "source": "The Guardian", "category": "world"},
    {"url": "http://feeds.reuters.com/reuters/topNews", "source": "Reuters", "category": "world"},
    {"url": "https://rss.cnn.com/rss/edition.rss", "source": "CNN", "category": "world"},
    # --- Science ---
    {"url": "https://www.sciencedaily.com/rss/all.xml", "source": "ScienceDaily", "category": "science"},
    {"url": "https://phys.org/rss-feed/", "source": "Phys.org", "category": "science"},
    # --- Business ---
    {"url": "https://feeds.bloomberg.com/markets/news.rss", "source": "Bloomberg", "category": "business"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "source": "CNBC", "category": "business"},
]


class RSSSource(BaseSource):
    """Crawl multiple RSS/Atom feeds."""

    name = "rss"

    def __init__(self, feeds: Optional[List[dict]] = None):
        self.feeds = feeds or DEFAULT_FEEDS

    def _parse_date(self, entry) -> Optional[datetime]:
        for field in ("published", "updated", "created"):
            val = getattr(entry, field, None)
            if val:
                try:
                    return dateparser.parse(val)
                except (ValueError, TypeError):
                    pass
        struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if struct:
            try:
                return datetime(*struct[:6])
            except Exception:
                pass
        return None

    def _get_summary(self, entry) -> str:
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        # Strip HTML tags simply
        from bs4 import BeautifulSoup
        text = BeautifulSoup(summary, "html.parser").get_text(separator=" ", strip=True)
        return text[:300] + "..." if len(text) > 300 else text

    def crawl(self) -> List[Article]:
        articles = []
        for feed_cfg in self.feeds:
            url = feed_cfg["url"]
            source = feed_cfg.get("source", url)
            category = feed_cfg.get("category", "general")
            try:
                d = feedparser.parse(url, agent=HEADERS["User-Agent"])
                for entry in d.entries[:20]:  # cap per feed
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    if not title or not link:
                        continue
                    articles.append(Article(
                        title=title,
                        url=link,
                        source=source,
                        summary=self._get_summary(entry),
                        timestamp=self._parse_date(entry),
                        category=category,
                    ))
                logger.info(f"[RSS] {source}: {len(d.entries)} entries")
            except Exception as e:
                logger.warning(f"[RSS] Failed {source}: {e}")
        return articles
