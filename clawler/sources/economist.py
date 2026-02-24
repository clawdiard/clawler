"""The Economist source — fetches articles from The Economist RSS feeds.

The Economist provides high-quality analysis on world affairs, business,
finance, science, and technology. Free RSS feeds (headlines + summaries)
are available at economist.com.

Enhanced features:
- 16 section feeds covering all Economist verticals including regional desks
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on section editorial weight, position decay, keyword specificity, and topic boost
- Sentence-boundary summary truncation at 300 chars
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with 📰 section and ✍️ author
- Provenance tags: economist:section, economist:category, economist:region, economist:tag
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

# ── Section feeds ──────────────────────────────────────────────────────
ECONOMIST_FEEDS: Dict[str, dict] = {
    "the-world-this-week": {"url": "https://www.economist.com/the-world-this-week/rss.xml", "label": "The World This Week", "default_cat": "world", "prominence": 0.55},
    "leaders": {"url": "https://www.economist.com/leaders/rss.xml", "label": "Leaders", "default_cat": "world", "prominence": 0.60},
    "briefing": {"url": "https://www.economist.com/briefing/rss.xml", "label": "Briefing", "default_cat": "world", "prominence": 0.58},
    "finance-and-economics": {"url": "https://www.economist.com/finance-and-economics/rss.xml", "label": "Finance & Economics", "default_cat": "business", "prominence": 0.55},
    "business": {"url": "https://www.economist.com/business/rss.xml", "label": "Business", "default_cat": "business", "prominence": 0.52},
    "science-and-technology": {"url": "https://www.economist.com/science-and-technology/rss.xml", "label": "Science & Technology", "default_cat": "science", "prominence": 0.55},
    "international": {"url": "https://www.economist.com/international/rss.xml", "label": "International", "default_cat": "world", "prominence": 0.50},
    "united-states": {"url": "https://www.economist.com/united-states/rss.xml", "label": "United States", "default_cat": "world", "prominence": 0.48, "region": "us"},
    "asia": {"url": "https://www.economist.com/asia/rss.xml", "label": "Asia", "default_cat": "world", "prominence": 0.47, "region": "asia"},
    "europe": {"url": "https://www.economist.com/europe/rss.xml", "label": "Europe", "default_cat": "world", "prominence": 0.47, "region": "europe"},
    "china": {"url": "https://www.economist.com/china/rss.xml", "label": "China", "default_cat": "world", "prominence": 0.48, "region": "china"},
    "middle-east-and-africa": {"url": "https://www.economist.com/middle-east-and-africa/rss.xml", "label": "Middle East & Africa", "default_cat": "world", "prominence": 0.45, "region": "mea"},
    "the-americas": {"url": "https://www.economist.com/the-americas/rss.xml", "label": "The Americas", "default_cat": "world", "prominence": 0.45, "region": "americas"},
    "britain": {"url": "https://www.economist.com/britain/rss.xml", "label": "Britain", "default_cat": "world", "prominence": 0.47, "region": "britain"},
    "culture": {"url": "https://www.economist.com/culture/rss.xml", "label": "Culture", "default_cat": "culture", "prominence": 0.42},
    "graphic-detail": {"url": "https://www.economist.com/graphic-detail/rss.xml", "label": "Graphic Detail", "default_cat": "science", "prominence": 0.48},
}

# Default sections to crawl when none specified
DEFAULT_SECTIONS = [
    "leaders", "briefing", "finance-and-economics", "business",
    "science-and-technology", "international", "united-states",
    "asia", "europe", "china",
]

# ── Keyword category detection ────────────────────────────────────────
SPECIFIC_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "chatgpt", "openai", "gpt-4", "gpt-5", "llm", "large language model",
        "generative ai", "copilot", "anthropic", "claude", "gemini ai",
        "computer vision", "natural language", "autonomous", "robotics",
        "stable diffusion", "midjourney", "transformer model", "training data",
    ],
    "security": [
        "cybersecurity", "cyber attack", "ransomware", "data breach", "hacking",
        "malware", "phishing", "zero-day", "vulnerability", "encryption",
        "surveillance", "espionage", "exploit", "intelligence agency",
        "sanctions evasion", "cyber warfare", "spyware",
    ],
    "crypto": [
        "bitcoin", "ethereum", "cryptocurrency", "blockchain", "defi",
        "stablecoin", "crypto exchange", "nft", "web3", "digital currency",
        "central bank digital", "cbdc",
    ],
    "health": [
        "pandemic", "vaccine", "clinical trial", "fda", "disease",
        "drug", "pharmaceutical", "biotech", "cancer", "mental health",
        "public health", "healthcare", "hospital", "virus", "antibiotic",
        "who", "epidemic", "obesity", "dementia", "malaria",
    ],
    "science": [
        "climate change", "global warming", "emissions", "renewable energy",
        "solar power", "wind energy", "nasa", "quantum computing", "physics",
        "biology", "genome", "crispr", "research study", "scientific",
        "spacex", "asteroid", "fusion", "telescope", "particle",
    ],
    "environment": [
        "carbon", "deforestation", "biodiversity", "pollution", "net zero",
        "sustainability", "fossil fuel", "drought", "flood", "wildfire",
        "ocean", "coral reef", "methane", "greenhouse",
    ],
    "business": [
        "earnings", "revenue", "ipo", "merger", "acquisition", "stock market",
        "antitrust", "monopoly", "regulation", "startup", "venture capital",
        "private equity", "corporate", "ceo", "management",
    ],
    "world": [
        "war", "conflict", "diplomacy", "election", "government",
        "congress", "parliament", "nato", "united nations", "geopolitics",
        "coup", "referendum", "migration", "refugee", "treaty",
    ],
    "culture": [
        "movie", "film", "tv show", "streaming", "netflix", "book review",
        "music", "art", "documentary", "theatre", "novel", "literary",
        "museum", "exhibition", "podcast",
    ],
    "education": [
        "university", "school", "student", "education", "curriculum",
        "academic", "research funding", "tuition", "scholarship",
    ],
    "design": [
        "architecture", "urban planning", "design", "infrastructure",
        "smart city", "housing", "construction",
    ],
    "gaming": [
        "video game", "gaming", "esports", "playstation", "xbox", "nintendo",
    ],
}

# Categories that get a quality boost when detected
BOOSTED_CATEGORIES = {"ai", "security", "crypto", "environment", "health"}


def _detect_category(title: str, summary: str, section_default: str) -> str:
    """Two-tier: specific keywords first, then section fallback."""
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
    return section_default


def _truncate_at_sentence(text: str, max_len: int = 300) -> str:
    """Truncate at nearest sentence boundary before max_len."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Find last sentence boundary
    for sep in [". ", "! ", "? "]:
        idx = truncated.rfind(sep)
        if idx > max_len * 0.4:
            return truncated[:idx + 1]
    return truncated[:max_len - 3] + "..."


def _compute_quality(
    section: str,
    prominence: float,
    category: str,
    section_default: str,
    position: int,
) -> float:
    """Quality score (0–1)."""
    # Position decay
    pos_factor = 1.0 / (1.0 + 0.04 * position)
    score = prominence * pos_factor

    # Boost for keyword-detected category (not just section fallback)
    if category != section_default:
        score = min(1.0, score + 0.06)

    # Boost for high-value categories
    if category in BOOSTED_CATEGORIES:
        score = min(1.0, score + 0.05)

    return round(min(1.0, score), 3)


class EconomistSource(BaseSource):
    """Fetch articles from The Economist RSS feeds.

    Parameters
    ----------
    limit : int
        Max articles per feed. Default 20.
    sections : list of str or None
        Section keys to crawl. None = DEFAULT_SECTIONS.
        Use ["all"] to crawl all 16 sections.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    exclude_sections : list of str or None
        Exclude these sections.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "economist"

    def __init__(
        self,
        limit: int = 20,
        sections: Optional[List[str]] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.limit = limit
        if sections and sections == ["all"]:
            self._sections = list(ECONOMIST_FEEDS.keys())
        elif sections:
            self._sections = [s for s in sections if s in ECONOMIST_FEEDS]
        else:
            self._sections = list(DEFAULT_SECTIONS)
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        active = self._sections
        if self.exclude_sections:
            active = [s for s in active if s not in self.exclude_sections]

        for section_key in active:
            feed_info = ECONOMIST_FEEDS[section_key]
            try:
                xml_text = self.fetch_url(feed_info["url"])
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, section_key, feed_info, seen_urls)
                all_articles.extend(parsed)
                logger.info(f"[Economist] {feed_info['label']}: {len(parsed)} articles")
            except Exception as e:
                logger.warning(f"[Economist] Failed to fetch {feed_info['label']}: {e}")

        # Filters
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if (a.quality_score or 0) >= self.min_quality]
        if self.category_filter:
            all_articles = [a for a in all_articles if a.category in self.category_filter]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[Economist] Total: {len(all_articles)} articles from {len(active)} section(s)")
        return all_articles

    def _parse_feed(
        self, xml_text: str, section_key: str, feed_info: dict, seen: Set[str]
    ) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[Economist] XML parse error for {section_key}: {e}")
            return articles

        ns = {"dc": "http://purl.org/dc/elements/1.1/", "atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item")

        label = feed_info["label"]
        default_cat = feed_info["default_cat"]
        prominence = feed_info["prominence"]
        region = feed_info.get("region")

        for position, item in enumerate(items[:self.limit]):
            try:
                art = self._parse_item(item, section_key, label, default_cat, prominence, region, position, seen, ns)
                if art:
                    articles.append(art)
            except Exception as e:
                logger.debug(f"[Economist] Skipping item in {section_key}: {e}")

        return articles

    def _parse_item(
        self, item, section_key: str, label: str, default_cat: str,
        prominence: float, region: Optional[str], position: int,
        seen: Set[str], ns: dict,
    ) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pubdate_el = item.find("pubDate")
        author_el = item.find("dc:creator", ns)
        if author_el is None:
            author_el = item.find("author")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Summary
        raw_summary = ""
        if desc_el is not None and desc_el.text:
            raw_summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        summary = _truncate_at_sentence(raw_summary, 300) if raw_summary else ""

        author = ""
        if author_el is not None and author_el.text:
            author = author_el.text.strip()

        ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)

        # Category detection
        category = _detect_category(title, summary, default_cat)
        quality = _compute_quality(section_key, prominence, category, default_cat, position)

        # Rich summary
        parts = []
        if author:
            parts.append(f"✍️ {author}")
        parts.append(f"📰 {label}")
        rich_summary = " · ".join(parts)
        if summary:
            rich_summary += f" — {summary}"

        # Provenance tags
        tags = [
            f"economist:section:{section_key}",
            f"economist:category:{category}",
        ]
        if region:
            tags.append(f"economist:region:{region}")
        if author:
            tags.append(f"economist:author:{author.lower()}")
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"economist:tag:{cat_el.text.strip().lower()}")

        return Article(
            title=title,
            url=url,
            source=f"The Economist ({label})",
            summary=rich_summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=quality,
        )


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse RFC 2822 / ISO dates."""
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
