"""Ars Technica source — fetches articles from arstechnica.com RSS feeds.

Ars Technica is a premier technology publication known for in-depth,
technically rigorous reporting on science, tech policy, gaming, and IT.

Enhanced features:
- 10 section feeds covering all Ars verticals
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on section prominence, position, keyword specificity, and author reputation
- Prominent author recognition (senior editors and long-form writers)
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with ✍️ author and 📰 section
- Provenance tags: ars:section, ars:category, ars:author, ars:tag
- Cross-section URL deduplication
- Quality-sorted output
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Section feeds — curated for quality and breadth
ARS_FEEDS: Dict[str, str] = {
    "main": "https://feeds.arstechnica.com/arstechnica/index",
    "tech-policy": "https://feeds.arstechnica.com/arstechnica/tech-policy",
    "science": "https://feeds.arstechnica.com/arstechnica/science",
    "gaming": "https://feeds.arstechnica.com/arstechnica/gaming",
    "gadgets": "https://feeds.arstechnica.com/arstechnica/gadgets",
    "ai": "https://feeds.arstechnica.com/arstechnica/ai",
    "security": "https://feeds.arstechnica.com/arstechnica/security",
    "cars": "https://feeds.arstechnica.com/arstechnica/cars",
    "apple": "https://feeds.arstechnica.com/arstechnica/apple",
    "staff-blogs": "https://feeds.arstechnica.com/arstechnica/staff-blogs",
}

# Section → default Clawler category mapping
SECTION_CATEGORY_MAP: Dict[str, str] = {
    "main": "tech",
    "tech-policy": "tech",
    "science": "science",
    "gaming": "gaming",
    "gadgets": "tech",
    "ai": "ai",
    "security": "security",
    "cars": "tech",
    "apple": "tech",
    "staff-blogs": "tech",
}

# Section prominence scores (editorial weight)
SECTION_PROMINENCE: Dict[str, float] = {
    "main": 0.55,
    "ai": 0.55,
    "science": 0.50,
    "security": 0.50,
    "tech-policy": 0.50,
    "gadgets": 0.45,
    "gaming": 0.45,
    "apple": 0.45,
    "cars": 0.40,
    "staff-blogs": 0.35,
}

# Prominent Ars Technica authors (senior editors / long-form writers)
PROMINENT_AUTHORS: Dict[str, float] = {
    "john timmer": 0.12,
    "timothy b. lee": 0.10,
    "ron amadeo": 0.10,
    "sean gallagher": 0.10,
    "kyle orland": 0.10,
    "samuel axon": 0.08,
    "ashley belanger": 0.10,
    "benj edwards": 0.10,
    "scharon harding": 0.08,
    "andrew cunningham": 0.08,
    "dan goodin": 0.12,
    "beth mole": 0.10,
    "jennifer ouellette": 0.08,
    "jonathan gitlin": 0.08,
    "kate cox": 0.08,
    "eric berger": 0.10,
}

# --- Keyword category detection ---
SPECIFIC_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "chatgpt", "openai", "gpt-4", "gpt-5", "llm", "large language model",
        "generative ai", "copilot", "anthropic", "claude", "gemini ai",
        "computer vision", "natural language", "autonomous", "robotics",
        "stable diffusion", "midjourney", "training data", "transformer model",
    ],
    "security": [
        "cybersecurity", "cyber attack", "ransomware", "data breach", "hacking",
        "malware", "phishing", "zero-day", "vulnerability", "encryption",
        "surveillance", "privacy breach", "espionage", "exploit", "backdoor",
        "password", "authentication", "spyware", "botnet", "ddos",
    ],
    "science": [
        "climate change", "global warming", "emissions", "renewable energy",
        "solar power", "wind energy", "nasa", "space launch", "satellite",
        "quantum computing", "physics", "biology", "genome", "crispr",
        "research study", "scientific", "spacex", "asteroid", "exoplanet",
        "particle physics", "fusion", "telescope", "mars", "jwst",
    ],
    "tech": [
        "software", "hardware", "processor", "chip", "semiconductor",
        "open source", "linux", "windows", "android", "ios", "api",
        "cloud computing", "data center", "5g", "broadband", "fiber",
        "startup", "silicon valley", "developer", "programming",
    ],
    "gaming": [
        "video game", "gaming", "esports", "playstation", "xbox", "nintendo",
        "game studio", "steam", "pc gaming", "console", "indie game",
        "rpg", "fps", "mmorpg", "game review", "game pass",
    ],
    "business": [
        "earnings", "revenue", "ipo", "merger", "acquisition", "stock",
        "antitrust", "monopoly", "ftc", "doj", "regulation", "lawsuit",
        "patent", "copyright", "trade", "tariff",
    ],
    "crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "blockchain", "defi",
        "stablecoin", "crypto exchange", "nft", "web3", "digital currency",
    ],
    "health": [
        "pandemic", "vaccine", "clinical trial", "fda", "disease",
        "drug", "pharmaceutical", "biotech", "cancer", "mental health",
        "public health", "healthcare", "hospital", "virus", "antibiotic",
    ],
    "world": [
        "war", "conflict", "sanctions", "diplomacy", "election",
        "government", "congress", "senate", "white house", "eu", "china",
    ],
    "culture": [
        "movie", "film", "tv show", "streaming", "netflix", "disney",
        "book review", "music", "art", "documentary",
    ],
    "automotive": [
        "electric vehicle", "ev", "tesla", "self-driving", "autonomous vehicle",
        "hybrid", "charging", "battery", "lidar", "adas",
    ],
    "space": [
        "spacex", "nasa", "orbit", "rocket", "launch", "iss",
        "moon", "mars", "satellite", "astronaut", "starship", "artemis",
    ],
}


def _detect_category(title: str, summary: str, section_category: str) -> str:
    """Two-tier category detection: specific keywords first, then section fallback."""
    text = f"{title} {summary}".lower()
    best_cat = None
    best_hits = 0
    for cat, keywords in SPECIFIC_CATEGORIES.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_cat = cat
    if best_cat and best_hits >= 1:
        return best_cat
    return section_category


def _compute_quality(
    section: str,
    category: str,
    section_category: str,
    position: int,
    author: str,
) -> float:
    """Quality score (0–1) based on section prominence, position, keyword specificity, and author."""
    base = SECTION_PROMINENCE.get(section, 0.40)
    # Position decay: first articles score higher
    position_factor = 1.0 / (1.0 + 0.05 * position)
    score = base * position_factor
    # Boost for specific keyword-detected category (not just section fallback)
    if category != section_category:
        score = min(1.0, score + 0.08)
    # Author reputation boost
    author_boost = PROMINENT_AUTHORS.get(author.lower(), 0.0)
    score = min(1.0, score + author_boost)
    return round(min(1.0, score), 3)


class ArsTechnicaSource(BaseSource):
    """Fetch articles from Ars Technica RSS feeds.

    Parameters
    ----------
    limit : int
        Max articles per feed. Default 25.
    feeds : list of str or None
        Section feeds to crawl. None = ['main', 'science', 'ai', 'security'].
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    exclude_sections : list of str or None
        Exclude these sections.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "arstechnica"

    def __init__(
        self,
        limit: int = 25,
        feeds: Optional[List[str]] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.limit = limit
        if feeds is not None:
            self._feeds = [f for f in feeds if f in ARS_FEEDS]
        else:
            self._feeds = ["main", "science", "ai", "security"]
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        active_feeds = self._feeds
        if self.exclude_sections:
            active_feeds = [f for f in active_feeds if f not in self.exclude_sections]

        for section in active_feeds:
            feed_url = ARS_FEEDS[section]
            try:
                xml_text = self.fetch_url(feed_url)
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, section, seen_urls)
                all_articles.extend(parsed)
                logger.info(f"[ArsTechnica] {section}: {len(parsed)} articles")
            except Exception as e:
                logger.warning(f"[ArsTechnica] Failed to fetch {section}: {e}")

        # Apply filters
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if (a.quality_score or 0) >= self.min_quality]

        if self.category_filter:
            all_articles = [a for a in all_articles if a.category in self.category_filter]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Global limit
        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[ArsTechnica] Total: {len(all_articles)} articles from {len(active_feeds)} section(s)")
        return all_articles

    def _parse_feed(
        self, xml_text: str, section: str, seen: Set[str]
    ) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[ArsTechnica] XML parse error for {section}: {e}")
            return articles

        ns = {"atom": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}

        items = root.findall(".//item")
        if not items:
            items = root.findall("atom:entry", ns)

        for position, item in enumerate(items[: self.limit]):
            try:
                article = self._parse_item(item, section, position, seen, ns)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[ArsTechnica] Skipping item in {section}: {e}")

        return articles

    def _parse_item(
        self, item, section: str, position: int, seen: Set[str], ns: dict
    ) -> Optional[Article]:
        # RSS 2.0
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pubdate_el = item.find("pubDate")
        author_el = item.find("dc:creator", ns)
        if author_el is None:
            author_el = item.find("author")

        # Atom fallback
        if title_el is None:
            title_el = item.find("atom:title", ns)
        if link_el is None:
            link_atom = item.find("atom:link[@rel='alternate']", ns)
            if link_atom is not None:
                link_text = link_atom.get("href", "")
            else:
                link_text = ""
        else:
            link_text = (link_el.text or "").strip()

        title = (title_el.text or "").strip() if title_el is not None else ""
        if not isinstance(link_text, str):
            link_text = ""
        url = link_text.strip()

        if not title or not url:
            return None

        if url in seen:
            return None
        seen.add(url)

        summary = ""
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
            if len(summary) > 300:
                summary = summary[:297] + "..."

        author = ""
        if author_el is not None and author_el.text:
            author = author_el.text.strip()

        ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)

        section_category = SECTION_CATEGORY_MAP.get(section, "tech")
        category = _detect_category(title, summary, section_category)
        quality = _compute_quality(section, category, section_category, position, author)

        # Build rich summary
        parts = []
        if author:
            parts.append(f"✍️ {author}")
        parts.append(f"📰 {section}")
        if summary:
            parts.append(summary)
        rich_summary = " · ".join(parts[:2])
        if summary:
            rich_summary += f" — {summary}"

        # Provenance tags
        tags = [
            f"ars:section:{section}",
            f"ars:category:{category}",
        ]
        if author:
            tags.append(f"ars:author:{author.lower()}")
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"ars:tag:{cat_el.text.strip().lower()}")

        return Article(
            title=title,
            url=url,
            source=f"Ars Technica ({section})",
            summary=rich_summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=quality,
        )


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse RFC 2822 / RFC 822 dates commonly used in RSS feeds."""
    if not raw:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None
