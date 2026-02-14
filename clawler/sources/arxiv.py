"""ArXiv source — fetches recent papers from the Atom API (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"

# Default categories to fetch (broad CS + physics highlights)
DEFAULT_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.SE"]


class ArXivSource(BaseSource):
    """Fetch recent papers from ArXiv's public Atom API."""

    name = "arxiv"
    timeout = 20

    def __init__(self, categories: List[str] = None, limit: int = 25):
        self.categories = categories or DEFAULT_CATEGORIES
        self.limit = limit

    def crawl(self) -> List[Article]:
        # Build query: OR across categories, sorted by submitted date
        cat_query = "+OR+".join(f"cat:{c}" for c in self.categories)
        url = (
            f"{ARXIV_API}?search_query={cat_query}"
            f"&sortBy=submittedDate&sortOrder=descending"
            f"&start=0&max_results={self.limit}"
        )

        text = self.fetch_url(url)
        if not text:
            return []

        return self._parse_feed(text)

    def _parse_feed(self, xml_text: str) -> List[Article]:
        """Parse ArXiv Atom feed into Articles using feedparser."""
        feed = feedparser.parse(xml_text)
        articles: List[Article] = []

        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            title = re.sub(r"\s+", " ", title)
            if not title:
                continue

            # Get the abstract link (html page)
            link_url = getattr(entry, "link", "").strip()
            if not link_url:
                continue

            # PDF link from alternate links
            pdf_url = ""
            for link in getattr(entry, "links", []):
                href = link.get("href", "")
                if link.get("title") == "pdf" or "pdf" in href:
                    pdf_url = href
                    break

            # Summary
            summary = getattr(entry, "summary", "").strip()
            summary = re.sub(r"\s+", " ", summary)
            if len(summary) > 300:
                summary = summary[:297] + "..."

            # Timestamp
            timestamp = None
            for field in ("published", "updated"):
                raw = getattr(entry, field, None)
                if raw:
                    try:
                        timestamp = dateparser.parse(raw)
                        break
                    except (ValueError, OverflowError):
                        pass

            # Authors
            authors = []
            for author in getattr(entry, "authors", []):
                name = author.get("name", "").strip()
                if name:
                    authors.append(name)
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += f" +{len(authors) - 3} more"

            # Categories / tags
            tags = []
            for tag in getattr(entry, "tags", []):
                term = tag.get("term", "")
                if term:
                    tags.append(term)

            category = self._map_category(tags)

            articles.append(Article(
                title=title,
                url=link_url,
                source="ArXiv",
                summary=summary,
                timestamp=timestamp,
                category=category,
                tags=tags,
                author=author_str,
                discussion_url=pdf_url,
            ))

        logger.info(f"[ArXiv] Parsed {len(articles)} papers")
        return articles

    @staticmethod
    def _map_category(tags: List[str]) -> str:
        """Map ArXiv categories to clawler categories."""
        tag_str = " ".join(tags).lower()
        if any(k in tag_str for k in ("cs.ai", "cs.lg", "cs.cl", "cs.cv", "cs.ne", "stat.ml")):
            return "tech"
        if any(k in tag_str for k in ("cs.se", "cs.pl", "cs.db", "cs.dc")):
            return "tech"
        if any(k in tag_str for k in ("physics", "quant-ph", "astro", "hep")):
            return "science"
        if any(k in tag_str for k in ("math",)):
            return "science"
        if any(k in tag_str for k in ("q-bio", "q-fin")):
            return "science"
        return "science"
