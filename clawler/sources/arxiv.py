"""ArXiv source — fetches recent papers from the Atom API (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from typing import List
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

        return self._parse_atom(text)

    def _parse_atom(self, xml_text: str) -> List[Article]:
        """Parse ArXiv Atom feed into Articles."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("[ArXiv] beautifulsoup4 required")
            return []

        import warnings
        try:
            from bs4 import XMLParsedAsHTMLWarning
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        except ImportError:
            pass
        soup = BeautifulSoup(xml_text, "html.parser")
        articles: List[Article] = []

        for entry in soup.find_all("entry"):
            title_tag = entry.find("title")
            if not title_tag:
                continue
            title = re.sub(r"\s+", " ", title_tag.get_text()).strip()
            if not title:
                continue

            # Get the abstract link (html page)
            link_url = ""
            pdf_url = ""
            for link in entry.find_all("link"):
                href = link.get("href", "")
                link_type = link.get("type", "")
                link_title = link.get("title", "")
                if link_title == "pdf" or "pdf" in href:
                    pdf_url = href
                elif "abs" in href or link_type == "text/html":
                    link_url = href
                elif not link_url and href:
                    link_url = href

            if not link_url:
                continue

            # Summary
            summary_tag = entry.find("summary")
            summary = ""
            if summary_tag:
                summary = re.sub(r"\s+", " ", summary_tag.get_text()).strip()
                # Truncate long abstracts
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            # Timestamp
            published = entry.find("published")
            timestamp = None
            if published:
                try:
                    ts_text = published.get_text().strip()
                    timestamp = datetime.fromisoformat(ts_text.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            # Authors
            authors = []
            for author_tag in entry.find_all("author"):
                name_tag = author_tag.find("name")
                if name_tag:
                    authors.append(name_tag.get_text().strip())
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += f" +{len(authors) - 3} more"

            # Categories / tags
            tags = []
            for cat in entry.find_all("category"):
                term = cat.get("term", "")
                if term:
                    tags.append(term)

            # Map to broad category
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
