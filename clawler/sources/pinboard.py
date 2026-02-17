"""Pinboard Popular source — trending community-curated bookmarks.

v10.21.0 enhancements:
- Multi-page scraping (popular, recent, popular/<tag>)
- Quality scoring (0–1) based on save count + tag richness
- Two-tier keyword category detection (12 specific categories before tag fallback)
- Save count extraction with human-readable formatting
- Tag filtering: filter_tags (whitelist) and exclude_tags (blacklist)
- Domain extraction from bookmark URLs
- min_saves and min_quality filters
- category_filter to restrict output categories
- global_limit with quality-sorted output
- Provenance tags: pinboard:tag:<t>, pinboard:domain:<host>, pinboard:category:<cat>, pinboard:page:<type>
- Cross-page URL deduplication
"""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from clawler.models import Article
from clawler.sources.base import HEADERS, BaseSource

logger = logging.getLogger(__name__)

PINBOARD_BASE = "https://pinboard.in"
PINBOARD_POPULAR_URL = f"{PINBOARD_BASE}/popular/"
PINBOARD_RECENT_URL = f"{PINBOARD_BASE}/recent/"

# ── Two-tier keyword categories ─────────────────────────────────────
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "ai", "artificial-intelligence", "machine-learning", "ml", "deep-learning",
        "neural", "llm", "gpt", "chatgpt", "openai", "transformer", "nlp",
        "computer-vision", "diffusion", "generative-ai", "rag",
    ],
    "security": [
        "security", "infosec", "privacy", "cybersecurity", "encryption",
        "hacking", "malware", "vulnerability", "pentest", "netsec", "zero-day",
        "ransomware", "phishing", "firewall", "authentication", "oauth",
    ],
    "crypto": [
        "crypto", "cryptocurrency", "bitcoin", "ethereum", "blockchain",
        "defi", "nft", "web3", "solana", "token",
    ],
    "science": [
        "science", "physics", "biology", "chemistry", "research", "math",
        "climate", "neuroscience", "astronomy", "quantum", "genomics",
        "paleontology", "ecology",
    ],
    "health": [
        "health", "medicine", "medical", "mental-health", "nutrition",
        "fitness", "wellness", "pharmaceutical", "epidemiology",
    ],
    "gaming": [
        "gaming", "games", "gamedev", "game-design", "indie-games",
        "esports", "unity", "unreal", "godot",
    ],
    "design": [
        "design", "ux", "ui", "typography", "css", "graphic-design",
        "figma", "accessibility", "a11y", "color", "illustration",
    ],
    "business": [
        "business", "finance", "economics", "startup", "investing",
        "management", "marketing", "saas", "entrepreneurship", "venture-capital",
    ],
    "world": [
        "politics", "world", "news", "war", "geopolitics", "democracy",
        "election", "diplomacy", "immigration", "human-rights",
    ],
    "culture": [
        "culture", "art", "music", "film", "books", "history", "philosophy",
        "literature", "cinema", "photography", "architecture",
    ],
    "education": [
        "education", "learning", "teaching", "mooc", "course", "tutorial",
        "university", "pedagogy",
    ],
    "environment": [
        "environment", "climate-change", "sustainability", "energy",
        "renewable", "solar", "wind", "conservation",
    ],
}


def _human_count(n: int) -> str:
    """Format count as human-readable string."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL, stripping www."""
    try:
        host = urlparse(url).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        return host if host else None
    except Exception:
        return None


def _parse_save_count(text: str) -> int:
    """Parse save count from Pinboard bookmark_count text like '42 saves' or '1.2k'."""
    if not text:
        return 0
    text = text.strip().lower().replace(",", "")
    m = re.search(r"([\d.]+)\s*k", text)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.search(r"([\d.]+)\s*m", text)
    if m:
        return int(float(m.group(1)) * 1_000_000)
    m = re.search(r"(\d+)", text)
    if m:
        return int(m.group(1))
    return 0


class PinboardSource(BaseSource):
    """Scrapes pinboard.in/popular for trending bookmarked links.

    Options:
        pages (list[str]): Page types to scrape. Default: ["popular"]
            Options: "popular", "recent", or "popular/<tag>" (e.g. "popular/python")
        filter_tags (list[str]): Only include bookmarks with at least one of these tags.
        exclude_tags (list[str]): Skip bookmarks with any of these tags.
        min_saves (int): Minimum save count to include (default 0).
        min_quality (float): Minimum quality score 0–1 (default 0).
        category_filter (list[str]): Only include these categories.
        global_limit (int): Max total articles returned (default 60).
        limit (int): Alias for global_limit.
    """

    name = "Pinboard Popular"
    source_type = "pinboard"

    def crawl(self, **kwargs) -> List[Article]:
        pages: List[str] = kwargs.get("pages", ["popular"])
        filter_tags: Optional[List[str]] = kwargs.get("filter_tags")
        exclude_tags: Optional[List[str]] = kwargs.get("exclude_tags")
        min_saves: int = kwargs.get("min_saves", 0)
        min_quality: float = kwargs.get("min_quality", 0.0)
        category_filter: Optional[List[str]] = kwargs.get("category_filter")
        global_limit: int = kwargs.get("global_limit", kwargs.get("limit", 60))

        filter_tags_set: Optional[Set[str]] = (
            {t.lower() for t in filter_tags} if filter_tags else None
        )
        exclude_tags_set: Optional[Set[str]] = (
            {t.lower() for t in exclude_tags} if exclude_tags else None
        )

        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        for page in pages:
            page_type = page.split("/")[0] if "/" in page else page
            url = self._page_url(page)
            try:
                articles = self._scrape_page(url, page_type, seen_urls)
                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"[Pinboard] Failed to scrape {url}: {e}")

        # Apply filters
        filtered: List[Article] = []
        for a in all_articles:
            tags_lower = {t.replace("pinboard:tag:", "").lower() for t in a.tags if t.startswith("pinboard:tag:")}

            if filter_tags_set and not (tags_lower & filter_tags_set):
                continue
            if exclude_tags_set and (tags_lower & exclude_tags_set):
                continue

            save_count = getattr(a, "_save_count", 0)
            if save_count < min_saves:
                continue

            if a.quality_score < min_quality:
                continue

            if category_filter and a.category not in category_filter:
                continue

            filtered.append(a)

        # Sort by quality descending
        filtered.sort(key=lambda a: a.quality_score, reverse=True)

        return filtered[:global_limit]

    def _page_url(self, page: str) -> str:
        """Build URL for a page type."""
        if page == "popular":
            return PINBOARD_POPULAR_URL
        if page == "recent":
            return PINBOARD_RECENT_URL
        if page.startswith("popular/"):
            tag = page.split("/", 1)[1]
            return f"{PINBOARD_BASE}/popular/t:{tag}/"
        return f"{PINBOARD_BASE}/{page}/"

    def _scrape_page(
        self, url: str, page_type: str, seen_urls: Set[str]
    ) -> List[Article]:
        articles: List[Article] = []
        html = self.fetch_url(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        bookmarks = soup.select(".bookmark")
        if not bookmarks:
            bookmarks = soup.select("#bookmarks .bookmark, .bookmarks .bookmark")

        for bm in bookmarks[:60]:
            link_tag = bm.select_one("a.bookmark_title")
            if not link_tag:
                continue

            bm_url = link_tag.get("href", "").strip()
            title = link_tag.get_text(strip=True)

            if not bm_url or not title:
                continue
            if bm_url in seen_urls:
                continue
            seen_urls.add(bm_url)

            # Tags
            tags: List[str] = []
            tag_elements = bm.select("a.tag")
            for t in tag_elements:
                tags.append(t.get_text(strip=True))

            # Save count
            save_count = 0
            count_el = bm.select_one(".bookmark_count")
            if count_el:
                save_count = _parse_save_count(count_el.get_text(strip=True))

            # Domain
            domain = _extract_domain(bm_url)

            # Category (two-tier)
            category = self._categorize_keywords(tags, title)

            # Quality score
            quality = self._quality_score(save_count, len(tags))

            # Build summary
            parts: List[str] = []
            if save_count:
                parts.append(f"🔖 {_human_count(save_count)} saves")
            if domain:
                parts.append(f"🔗 {domain}")
            if tags:
                parts.append(f"🏷 {', '.join(tags[:5])}")
            summary = " · ".join(parts)

            # Provenance tags
            prov_tags: List[str] = [f"pinboard:page:{page_type}"]
            for t in tags:
                prov_tags.append(f"pinboard:tag:{t.lower()}")
            if domain:
                prov_tags.append(f"pinboard:domain:{domain}")
            prov_tags.append(f"pinboard:category:{category}")

            article = Article(
                title=title,
                url=bm_url,
                source=self.name,
                category=category,
                timestamp=datetime.now(timezone.utc),
                summary=summary,
                tags=prov_tags,
                quality_score=quality,
            )
            # Stash save_count for filtering
            article._save_count = save_count  # type: ignore[attr-defined]
            articles.append(article)

        logger.info(f"[Pinboard] Fetched {len(articles)} bookmarks from {url}")
        return articles

    @staticmethod
    def _quality_score(save_count: int, tag_count: int) -> float:
        """Compute quality score 0–1.

        Pinboard popular bookmarks are community-curated, so baseline is 0.4.
        Save count drives most of the score (logarithmic),
        tag richness provides a small boost.
        """
        baseline = 0.4
        # Save component: log10 scale, 10 saves ≈ 0.55, 100 ≈ 0.7, 1000 ≈ 0.85
        save_component = 0.0
        if save_count > 0:
            save_component = min(0.5, math.log10(save_count + 1) / 6.0)
        # Tag richness: 0–0.1 bonus
        tag_bonus = min(0.1, tag_count * 0.02)
        return min(1.0, baseline + save_component + tag_bonus)

    @staticmethod
    def _categorize_keywords(tags: List[str], title: str) -> str:
        """Two-tier category detection: keywords first, then tag set fallback."""
        # Combine tags + title words for keyword matching
        text_tokens = {t.lower() for t in tags}
        text_tokens.update(re.split(r"[\s\-_/]+", title.lower()))

        # Tier 1: specific keyword categories
        best_cat = None
        best_hits = 0
        for cat, keywords in KEYWORD_CATEGORIES.items():
            hits = sum(1 for kw in keywords if kw in text_tokens)
            if hits > best_hits:
                best_hits = hits
                best_cat = cat

        if best_cat and best_hits >= 1:
            return best_cat

        # Tier 2: broad tag-set fallback (original logic)
        tag_set = {t.lower() for t in tags}
        if tag_set & {"programming", "software", "python", "javascript", "rust", "golang", "linux", "devops", "api"}:
            return "tech"
        return "tech"

    def _categorize(self, tags: List[str]) -> str:
        """Legacy method — delegates to keyword-based categorization."""
        return self._categorize_keywords(tags, "")
