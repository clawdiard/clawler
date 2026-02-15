"""Pinboard Popular source — trending community-curated bookmarks."""
import logging
from datetime import datetime, timezone
from typing import List
from bs4 import BeautifulSoup
from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

PINBOARD_POPULAR_URL = "https://pinboard.in/popular/"


class PinboardSource(BaseSource):
    """Scrapes pinboard.in/popular for trending bookmarked links."""

    name = "Pinboard Popular"
    source_type = "pinboard"

    def crawl(self) -> List[Article]:
        articles = []
        try:
            resp = self.session.get(
                PINBOARD_POPULAR_URL,
                headers=HEADERS,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Pinboard popular page has bookmark entries with class "bookmark"
            bookmarks = soup.select(".bookmark")
            if not bookmarks:
                # Fallback: try finding links in the main content area
                bookmarks = soup.select("#bookmarks .bookmark, .bookmarks .bookmark")

            for bm in bookmarks[:30]:
                link_tag = bm.select_one("a.bookmark_title")
                if not link_tag:
                    continue

                url = link_tag.get("href", "").strip()
                title = link_tag.get_text(strip=True)

                if not url or not title:
                    continue

                # Extract tag list if available
                tags = []
                tag_elements = bm.select("a.tag")
                for t in tag_elements:
                    tags.append(t.get_text(strip=True))

                # Extract save count if available
                description = ""
                count_el = bm.select_one(".bookmark_count")
                if count_el:
                    description = count_el.get_text(strip=True)
                if tags:
                    tag_str = ", ".join(tags[:5])
                    description = f"Tags: {tag_str}" + (f" | {description}" if description else "")

                articles.append(Article(
                    title=title,
                    url=url,
                    source=self.name,
                    category=self._categorize(tags),
                    timestamp=datetime.now(timezone.utc),
                    summary=description or "",
                ))

            logger.info(f"[Pinboard] Fetched {len(articles)} popular bookmarks")
        except Exception as e:
            logger.error(f"[Pinboard] Failed to fetch popular bookmarks: {e}")
            raise

        return articles

    @staticmethod
    def _categorize(tags: List[str]) -> str:
        """Map Pinboard tags to Clawler categories."""
        tag_set = {t.lower() for t in tags}
        if tag_set & {"security", "infosec", "privacy", "cybersecurity", "encryption"}:
            return "security"
        if tag_set & {"science", "physics", "biology", "research", "math", "climate"}:
            return "science"
        if tag_set & {"business", "finance", "economics", "startup", "investing"}:
            return "business"
        if tag_set & {"culture", "art", "music", "film", "books", "history", "philosophy"}:
            return "culture"
        if tag_set & {"politics", "world", "news", "war", "geopolitics"}:
            return "world"
        return "tech"
