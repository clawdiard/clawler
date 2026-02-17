"""ArXiv source — fetches recent papers from the Atom API (no key needed)."""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"

# Default categories to fetch (broad CS + physics highlights)
DEFAULT_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.SE"]

# Expanded category mapping — specific ArXiv categories to clawler categories
CATEGORY_MAP: Dict[str, str] = {
    # AI / Machine Learning
    "cs.ai": "ai", "cs.lg": "ai", "cs.cl": "ai", "cs.cv": "ai",
    "cs.ne": "ai", "stat.ml": "ai", "cs.ma": "ai", "cs.ir": "ai",
    # Security
    "cs.cr": "security",
    # Tech / CS
    "cs.se": "tech", "cs.pl": "tech", "cs.db": "tech", "cs.dc": "tech",
    "cs.ds": "tech", "cs.hc": "tech", "cs.ni": "tech", "cs.os": "tech",
    "cs.pf": "tech", "cs.sy": "tech", "cs.fl": "tech", "cs.cc": "tech",
    "cs.cg": "tech", "cs.dm": "tech", "cs.gt": "tech", "cs.it": "tech",
    "cs.lo": "tech", "cs.mm": "tech", "cs.ms": "tech", "cs.ro": "tech",
    "cs.sc": "tech", "cs.sd": "tech", "cs.si": "tech",
    # Science — physics
    "astro-ph": "science", "cond-mat": "science", "gr-qc": "science",
    "hep-ex": "science", "hep-lat": "science", "hep-ph": "science",
    "hep-th": "science", "math-ph": "science", "nlin": "science",
    "nucl-ex": "science", "nucl-th": "science", "physics": "science",
    "quant-ph": "science",
    # Science — math
    "math": "science",
    # Science — bio / quantitative
    "q-bio": "science",
    # Finance
    "q-fin": "business",
    # Electrical engineering
    "eess": "tech",
    # Stats (non-ML)
    "stat.ap": "science", "stat.co": "science", "stat.me": "science",
    "stat.ot": "science", "stat.th": "science",
    # Health-adjacent
    "q-bio.nc": "health", "q-bio.qm": "health", "q-bio.gn": "health",
}

# Keywords in title for category boost
TITLE_KEYWORDS: Dict[str, str] = {
    "llm": "ai", "large language": "ai", "transformer": "ai", "diffusion model": "ai",
    "neural network": "ai", "reinforcement learn": "ai", "deep learn": "ai",
    "gpt": "ai", "bert": "ai", "attention mechanism": "ai", "fine-tun": "ai",
    "robot": "ai", "autonomous": "ai",
    "security": "security", "vulnerab": "security", "attack": "security",
    "privacy": "security", "encrypt": "security", "malware": "security",
    "blockchain": "crypto", "cryptocurrency": "crypto", "decentral": "crypto",
    "medical": "health", "clinical": "health", "drug": "health", "patient": "health",
    "genomic": "health", "biomedic": "health",
    "climate": "science", "quantum": "science", "galaxy": "science",
}


class ArXivSource(BaseSource):
    """Fetch recent papers from ArXiv's public Atom API."""

    name = "arxiv"
    timeout = 20

    def __init__(
        self,
        categories: List[str] = None,
        limit: int = 25,
        per_category: bool = False,
        per_category_limit: int = 10,
        min_authors: int = 0,
        include_pdf_link: bool = True,
    ):
        self.categories = categories or DEFAULT_CATEGORIES
        self.limit = limit
        self.per_category = per_category
        self.per_category_limit = per_category_limit
        self.min_authors = min_authors
        self.include_pdf_link = include_pdf_link

    def crawl(self) -> List[Article]:
        if self.per_category:
            return self._crawl_per_category()
        return self._crawl_combined()

    def _crawl_combined(self) -> List[Article]:
        """Single query across all categories (original behavior)."""
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

    def _crawl_per_category(self) -> List[Article]:
        """Separate query per category with cross-category deduplication."""
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        for cat in self.categories:
            url = (
                f"{ARXIV_API}?search_query=cat:{cat}"
                f"&sortBy=submittedDate&sortOrder=descending"
                f"&start=0&max_results={self.per_category_limit}"
            )
            text = self.fetch_url(url)
            if not text:
                continue
            articles = self._parse_feed(text, source_category=cat)
            for a in articles:
                if a.url not in seen_urls:
                    seen_urls.add(a.url)
                    all_articles.append(a)

        # Sort by timestamp descending, apply global limit
        all_articles.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        if self.limit:
            all_articles = all_articles[: self.limit]

        logger.info(f"[ArXiv] Per-category crawl: {len(all_articles)} papers from {len(self.categories)} categories")
        return all_articles

    def _parse_feed(self, xml_text: str, source_category: str = None) -> List[Article]:
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

            # Summary / abstract
            raw_summary = getattr(entry, "summary", "").strip()
            raw_summary = re.sub(r"\s+", " ", raw_summary)
            summary = self._build_summary(raw_summary, title)

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

            # Apply min_authors filter
            if len(authors) < self.min_authors:
                continue

            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += f" +{len(authors) - 3} more"

            # Categories / tags
            tags = []
            primary_cat = None
            for tag in getattr(entry, "tags", []):
                term = tag.get("term", "")
                if term:
                    tags.append(term)
                    if primary_cat is None:
                        primary_cat = term

            # Add provenance tags
            if primary_cat:
                tags.append(f"arxiv:primary:{primary_cat}")
            if source_category:
                tags.append(f"arxiv:query:{source_category}")
            tags.append(f"arxiv:authors:{len(authors)}")

            # ArXiv paper ID extraction
            arxiv_id = self._extract_arxiv_id(link_url)
            if arxiv_id:
                tags.append(f"arxiv:id:{arxiv_id}")

            category = self._map_category(tags, title)

            # Quality score based on author count and category specificity
            quality_score = self._compute_quality(authors, tags, title)

            # Build enriched summary
            parts = []
            if author_str:
                parts.append(f"👤 {author_str}")
            if primary_cat:
                parts.append(f"📂 {primary_cat}")
            parts.append(summary)
            if self.include_pdf_link and pdf_url:
                parts.append(f"📄 PDF: {pdf_url}")
            enriched_summary = " · ".join(parts[:2])
            if len(parts) > 2:
                enriched_summary += f"\n{parts[2]}"
            if len(parts) > 3:
                enriched_summary += f"\n{parts[3]}"

            articles.append(Article(
                title=title,
                url=link_url,
                source="ArXiv",
                summary=enriched_summary,
                timestamp=timestamp,
                category=category,
                tags=tags,
                author=author_str,
                discussion_url=pdf_url,
                quality_score=quality_score,
            ))

        logger.info(f"[ArXiv] Parsed {len(articles)} papers")
        return articles

    @staticmethod
    def _build_summary(abstract: str, title: str) -> str:
        """Truncate abstract to a meaningful sentence boundary near 280 chars."""
        if len(abstract) <= 280:
            return abstract
        # Try to break at sentence boundary
        truncated = abstract[:300]
        last_period = truncated.rfind(". ")
        if last_period > 150:
            return truncated[: last_period + 1]
        return abstract[:277] + "..."

    @staticmethod
    def _extract_arxiv_id(url: str) -> Optional[str]:
        """Extract ArXiv paper ID from URL (e.g. 2401.12345)."""
        m = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", url)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _map_category(tags: List[str], title: str = "") -> str:
        """Map ArXiv categories to clawler categories with title keyword boost."""
        # First: check title keywords for specific categories
        title_lower = title.lower()
        for keyword, cat in TITLE_KEYWORDS.items():
            if keyword in title_lower:
                return cat

        # Second: check arxiv category tags against specific map
        for tag in tags:
            tag_lower = tag.lower()
            # Direct match
            if tag_lower in CATEGORY_MAP:
                return CATEGORY_MAP[tag_lower]
            # Prefix match (e.g. "astro-ph.CO" → "astro-ph")
            prefix = tag_lower.split(".")[0]
            if prefix in CATEGORY_MAP:
                return CATEGORY_MAP[prefix]

        return "science"

    @staticmethod
    def _compute_quality(authors: list, tags: list, title: str) -> float:
        """Quality score 0–1 based on author team size and specificity signals."""
        score = 0.5  # baseline

        # More authors → collaborative / institutional work → slight boost
        n = len(authors)
        if n >= 5:
            score += 0.15
        elif n >= 3:
            score += 0.1
        elif n >= 2:
            score += 0.05

        # Multiple ArXiv categories → cross-disciplinary
        arxiv_cats = [t for t in tags if not t.startswith("arxiv:") and "." in t]
        if len(arxiv_cats) >= 3:
            score += 0.1
        elif len(arxiv_cats) >= 2:
            score += 0.05

        # Title keyword matches for hot topics
        title_lower = title.lower()
        hot_keywords = ["llm", "gpt", "transformer", "diffusion", "quantum", "climate", "crispr"]
        if any(k in title_lower for k in hot_keywords):
            score += 0.1

        return min(score, 1.0)
