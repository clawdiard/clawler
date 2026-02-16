"""Medium source — fetches articles via Medium's public RSS feeds (no API key needed)."""
import logging
import math
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Default Medium feeds: mix of popular tags and notable publications
DEFAULT_TAG_FEEDS = [
    "artificial-intelligence",
    "machine-learning",
    "programming",
    "technology",
    "data-science",
    "startup",
    "product-management",
    "cybersecurity",
    "design",
    "science",
    "economics",
    "cryptocurrency",
    "javascript",
    "python",
    "devops",
    "ux",
    "business",
    "productivity",
    "software-engineering",
    "climate-change",
]

DEFAULT_PUBLICATION_FEEDS = [
    "towards-data-science",
    "better-programming",
    "the-startup",
    "hackernoon",  # legacy medium feed
    "netflix-techblog",
    "airbnb-engineering",
    "google-developers",
    "slack-eng",
    "flutter",
    "javascript-in-plain-english",
]

# Specific category mappings — checked first (more precise than generic)
SPECIFIC_CATEGORY_MAP = {
    "artificial-intelligence": "ai",
    "machine-learning": "ai",
    "deep-learning": "ai",
    "nlp": "ai",
    "computer-vision": "ai",
    "neural-networks": "ai",
    "generative-ai": "ai",
    "llm": "ai",
    "chatgpt": "ai",
    "cybersecurity": "security",
    "infosec": "security",
    "privacy": "security",
    "hacking": "security",
    "cryptocurrency": "crypto",
    "bitcoin": "crypto",
    "ethereum": "crypto",
    "blockchain": "crypto",
    "web3": "crypto",
    "defi": "crypto",
    "nft": "crypto",
    "design": "design",
    "ux": "design",
    "ui": "design",
    "ux-design": "design",
    "graphic-design": "design",
    "product-design": "design",
    "gaming": "gaming",
    "game-development": "gaming",
    "unity": "gaming",
    "unreal-engine": "gaming",
    "health": "health",
    "mental-health": "health",
    "fitness": "health",
    "medicine": "health",
    "wellness": "health",
    "nutrition": "health",
    "science": "science",
    "physics": "science",
    "biology": "science",
    "neuroscience": "science",
    "climate-change": "science",
    "space": "science",
    "astronomy": "science",
    "education": "education",
    "learning": "education",
    "teaching": "education",
    "startup": "business",
    "entrepreneurship": "business",
    "product-management": "business",
    "economics": "business",
    "marketing": "business",
    "leadership": "business",
    "venture-capital": "business",
    "finance": "business",
    "investing": "business",
    "business": "business",
    "productivity": "business",
    "writing": "culture",
    "books": "culture",
    "philosophy": "culture",
    "psychology": "culture",
    "relationships": "culture",
    "travel": "culture",
    "politics": "world",
    "society": "world",
    "social-media": "culture",
}

# Generic fallback (tag → tech)
GENERIC_TECH_TAGS = {
    "programming", "technology", "data-science", "javascript", "python",
    "devops", "software-engineering", "react", "nodejs", "typescript",
    "golang", "rust", "swift", "kotlin", "java", "docker", "kubernetes",
    "aws", "cloud-computing", "microservices", "api", "frontend",
    "backend", "mobile-development", "ios", "android", "flutter",
    "data-engineering", "sql", "database", "linux", "open-source",
}

# Publication → category overrides
PUBLICATION_CATEGORY_MAP = {
    "towards-data-science": "ai",
    "better-programming": "tech",
    "the-startup": "business",
    "hackernoon": "tech",
    "netflix-techblog": "tech",
    "airbnb-engineering": "tech",
    "google-developers": "tech",
    "slack-eng": "tech",
    "flutter": "tech",
    "javascript-in-plain-english": "tech",
}

# Average reading speed (words per minute)
_WPM = 238


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"&[a-zA-Z]+;", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _estimate_reading_time(html_content: str) -> int:
    """Estimate reading time in minutes from HTML content."""
    text = _strip_html(html_content)
    words = len(text.split())
    return max(1, round(words / _WPM))


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse RSS date formats."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_categories(item: ET.Element) -> List[str]:
    """Extract category tags from an RSS item."""
    tags = []
    for cat in item.findall("category"):
        text = (cat.text or "").strip()
        if text:
            tags.append(text.lower())
    return tags[:10]


def _detect_category(tags: List[str], label: str, feed_type: str) -> str:
    """Detect category: specific tags first, then publication map, then generic tech, then fallback."""
    # Check specific categories first (prefer non-generic)
    for tag in tags:
        if tag in SPECIFIC_CATEGORY_MAP:
            return SPECIFIC_CATEGORY_MAP[tag]

    # Check label against specific map
    if label in SPECIFIC_CATEGORY_MAP:
        return SPECIFIC_CATEGORY_MAP[label]

    # Publication category override
    if feed_type == "publication" and label in PUBLICATION_CATEGORY_MAP:
        return PUBLICATION_CATEGORY_MAP[label]

    # Generic tech tags
    for tag in tags:
        if tag in GENERIC_TECH_TAGS:
            return "tech"
    if label in GENERIC_TECH_TAGS:
        return "tech"

    return "tech"


def _compute_quality_score(reading_time: int, tag_count: int) -> float:
    """Compute quality score 0–1 based on reading time and tag richness.

    Longer, well-tagged articles score higher. Short listicles score lower.
    """
    # Reading time component: peaks around 5-10 min (ideal Medium article length)
    time_score = min(1.0, math.log1p(reading_time) / math.log1p(12))
    # Tag richness: more tags = better categorized = likely higher quality
    tag_score = min(1.0, tag_count / 5)
    return round(0.7 * time_score + 0.3 * tag_score, 2)


class MediumSource(BaseSource):
    """Fetches articles from Medium via public RSS feeds."""

    name = "medium"

    def __init__(
        self,
        tag_feeds: Optional[List[str]] = None,
        publication_feeds: Optional[List[str]] = None,
        user_feeds: Optional[List[str]] = None,
        max_per_feed: int = 5,
        min_reading_time: int = 0,
        limit: Optional[int] = None,
    ):
        self.tag_feeds = tag_feeds if tag_feeds is not None else DEFAULT_TAG_FEEDS
        self.publication_feeds = publication_feeds if publication_feeds is not None else DEFAULT_PUBLICATION_FEEDS
        self.user_feeds = user_feeds or []
        self.max_per_feed = max_per_feed
        self.min_reading_time = min_reading_time
        self.limit = limit

    def _build_feed_urls(self) -> List[tuple]:
        """Build (url, label, feed_type) triples for all configured feeds."""
        urls = []
        for tag in self.tag_feeds:
            urls.append((f"https://medium.com/feed/tag/{tag}", tag, "tag"))
        for pub in self.publication_feeds:
            urls.append((f"https://medium.com/feed/{pub}", pub, "publication"))
        for user in self.user_feeds:
            handle = user.lstrip("@")
            urls.append((f"https://medium.com/feed/@{handle}", f"@{handle}", "user"))
        return urls

    def _parse_feed(self, xml_text: str, label: str, feed_type: str) -> List[Article]:
        """Parse RSS XML into Article objects."""
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"[Medium] XML parse error for {label}: {e}")
            return []

        articles = []
        # Handle both RSS 2.0 (<channel><item>) structures
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")

        for item in items[: self.max_per_feed]:
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            if not title or not url:
                continue

            # Clean tracking params from Medium URLs
            if "?" in url:
                url = url.split("?")[0]

            # Extract description/content
            content_encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            raw_desc = item.findtext("description") or ""
            full_html = content_encoded or raw_desc
            description = _strip_html(full_html)[:500]

            # Reading time estimation
            reading_time = _estimate_reading_time(full_html)

            # Filter by minimum reading time
            if reading_time < self.min_reading_time:
                continue

            # Author — Medium uses dc:creator
            author = (
                item.findtext("{http://purl.org/dc/elements/1.1/}creator")
                or item.findtext("author")
                or ""
            ).strip()

            # Timestamp
            pub_date = item.findtext("pubDate") or ""
            timestamp = _parse_date(pub_date)

            # Tags from RSS categories
            tags = _extract_categories(item)

            # Category detection (specific > publication > generic tech)
            category = _detect_category(tags, label, feed_type)

            # Build rich summary with reading time
            summary_parts = []
            if author:
                summary_parts.append(f"by {author}")
            summary_parts.append(f"📖 {reading_time} min read")
            summary_parts.append(description[:250])
            summary = " — ".join(summary_parts)

            # Quality scoring
            quality_score = _compute_quality_score(reading_time, len(tags))

            # Provenance tags
            provenance_tags = [f"medium:{feed_type}:{label}"]
            for t in tags[:5]:
                provenance_tags.append(f"medium:tag:{t}")

            articles.append(
                Article(
                    title=title,
                    url=url,
                    source="medium",
                    summary=summary[:300],
                    timestamp=timestamp,
                    category=category,
                    quality_score=quality_score,
                    tags=provenance_tags,
                    author=author,
                )
            )

        return articles

    def crawl(self) -> List[Article]:
        feed_urls = self._build_feed_urls()
        all_articles: List[Article] = []
        seen_urls = set()

        for url, label, feed_type in feed_urls:
            xml_text = self.fetch_url(url)
            articles = self._parse_feed(xml_text, label, feed_type)
            for a in articles:
                if a.url not in seen_urls:
                    seen_urls.add(a.url)
                    all_articles.append(a)

        if self.limit is not None:
            all_articles = all_articles[: self.limit]

        logger.info(f"[Medium] Fetched {len(all_articles)} articles from {len(feed_urls)} feeds")
        return all_articles
