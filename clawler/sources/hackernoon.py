"""Hacker Noon source — tech articles via public RSS feeds.

Enhanced with:
- Multiple topic feeds (latest, tagged topics)
- Reading time estimation from content word count
- Two-tier keyword category detection (12 specific categories)
- Quality scoring (0–1) based on reading time + tag richness + topic specificity
- Author extraction with provenance tags
- Filters: min_reading_time, min_quality, category_filter, global_limit
- Cross-feed URL deduplication
- Quality-sorted output
"""
import logging
import math
import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree as ET

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# ── Feed URLs ────────────────────────────────────────────────────────
BASE_FEED = "https://hackernoon.com/feed"
TAGGED_FEEDS: Dict[str, str] = {
    "ai":              "https://hackernoon.com/tagged/artificial-intelligence/feed",
    "programming":     "https://hackernoon.com/tagged/programming/feed",
    "blockchain":      "https://hackernoon.com/tagged/blockchain/feed",
    "startups":        "https://hackernoon.com/tagged/startups/feed",
    "cybersecurity":   "https://hackernoon.com/tagged/cybersecurity/feed",
    "devops":          "https://hackernoon.com/tagged/devops/feed",
    "web-development": "https://hackernoon.com/tagged/web-development/feed",
    "data-science":    "https://hackernoon.com/tagged/data-science/feed",
    "gaming":          "https://hackernoon.com/tagged/gaming/feed",
    "design":          "https://hackernoon.com/tagged/design/feed",
}

# ── Keyword → category (specific first, generic last) ────────────────
_SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "ai":          ["ai", "artificial-intelligence", "machine-learning", "deep-learning",
                    "neural-network", "llm", "chatgpt", "gpt", "openai", "transformer",
                    "nlp", "computer-vision", "reinforcement-learning", "generative-ai",
                    "stable-diffusion", "midjourney", "langchain", "rag", "fine-tuning",
                    "data-science", "tensorflow", "pytorch", "hugging-face"],
    "security":    ["security", "cybersecurity", "privacy", "hacking", "infosec",
                    "vulnerability", "encryption", "malware", "ransomware", "zero-day",
                    "pentesting", "authentication", "oauth", "sso", "firewall"],
    "crypto":      ["blockchain", "crypto", "cryptocurrency", "web3", "bitcoin",
                    "ethereum", "defi", "nft", "solidity", "smart-contract",
                    "dao", "dapp", "token", "mining", "wallet"],
    "health":      ["health", "healthcare", "biotech", "medical", "mental-health",
                    "fitness", "wellness", "telemedicine", "drug-discovery"],
    "science":     ["science", "space", "physics", "biology", "chemistry", "climate",
                    "astronomy", "neuroscience", "genetics", "quantum"],
    "business":    ["startup", "business", "marketing", "entrepreneurship",
                    "venture-capital", "saas", "product-management", "growth",
                    "remote-work", "freelancing", "leadership", "management"],
    "gaming":      ["gaming", "game-development", "gamedev", "unity", "unreal",
                    "esports", "game-design", "indie-game", "metaverse", "vr"],
    "design":      ["design", "ux", "ui", "user-experience", "figma", "css",
                    "web-design", "graphic-design", "accessibility", "typography"],
    "world":       ["politics", "geopolitics", "government", "policy", "law",
                    "regulation", "international"],
    "culture":     ["culture", "media", "entertainment", "music", "film",
                    "books", "writing", "creativity", "social-media"],
    "education":   ["education", "learning", "tutorial", "bootcamp", "mooc",
                    "edtech", "teaching", "online-learning"],
    "environment": ["environment", "climate-change", "sustainability", "renewable",
                    "green-energy", "carbon", "recycling", "pollution"],
}

_GENERIC_TECH_KEYWORDS: Set[str] = {
    "programming", "software", "technology", "javascript", "python", "rust",
    "golang", "typescript", "react", "nodejs", "docker", "kubernetes",
    "api", "database", "cloud", "aws", "linux", "devops", "git",
    "microservices", "serverless", "open-source", "coding", "web-development",
    "frontend", "backend", "mobile", "ios", "android", "flutter",
}

# Words per minute for reading time estimate
_WPM = 238


def _detect_category(tags: List[str], title: str = "") -> str:
    """Two-tier keyword category detection: specific categories first, generic tech last."""
    combined = set(t.lower().replace(" ", "-") for t in tags)
    # Also check title words
    title_words = set(re.findall(r'[a-z][a-z0-9-]+', title.lower()))
    combined |= title_words

    # Specific categories first
    for cat, keywords in _SPECIFIC_KEYWORDS.items():
        if combined & set(keywords):
            return cat

    # Generic tech
    if combined & _GENERIC_TECH_KEYWORDS:
        return "tech"

    return "tech"


def _estimate_reading_time(html_content: str) -> int:
    """Estimate reading time in minutes from HTML content."""
    text = re.sub(r"<[^>]+>", "", html_content)
    words = len(text.split())
    return max(1, round(words / _WPM))


def _compute_quality(reading_time: int, tag_count: int, has_specific_category: bool) -> float:
    """Quality score 0–1 based on reading time, tag richness, topic specificity.

    - Reading time (60%): logarithmic, 3min baseline → 0.4, 8min → 0.7, 15+ → 0.85
    - Tag richness (20%): more tags = better classified; 5 tags → 0.15, 10+ → 0.2
    - Specific category boost (20%): non-generic tech articles get +0.15
    """
    # Reading time component (0–0.6)
    rt_score = min(0.6, 0.6 * math.log10(max(1, reading_time)) / math.log10(20))

    # Tag richness (0–0.2)
    tag_score = min(0.2, 0.2 * min(tag_count, 10) / 10)

    # Specificity boost (0–0.2)
    spec_score = 0.15 if has_specific_category else 0.0

    return round(min(1.0, rt_score + tag_score + spec_score), 3)


def _fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class HackerNoonSource(BaseSource):
    """Fetch articles from Hacker Noon RSS feeds with quality scoring and filtering."""

    name = "hackernoon"

    def __init__(
        self,
        limit: int = 25,
        feeds: Optional[List[str]] = None,
        min_reading_time: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.limit = limit
        self.feeds = feeds  # list of tagged feed keys, or None for main + all tagged
        self.min_reading_time = min_reading_time
        self.min_quality = min_quality
        self.category_filter = set(category_filter) if category_filter else None
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        # Build feed list
        feed_urls: Dict[str, str] = {"latest": BASE_FEED}
        if self.feeds:
            for key in self.feeds:
                if key in TAGGED_FEEDS:
                    feed_urls[key] = TAGGED_FEEDS[key]
        else:
            feed_urls.update(TAGGED_FEEDS)

        for feed_name, url in feed_urls.items():
            parsed = self._parse_feed(url, feed_name, seen_urls)
            articles.extend(parsed)

        # Sort by quality descending
        articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Apply global limit
        if self.global_limit:
            articles = articles[: self.global_limit]

        logger.info(f"[HackerNoon] Fetched {len(articles)} articles from {len(feed_urls)} feeds")
        return articles

    def _parse_feed(self, url: str, feed_name: str, seen: Set[str]) -> List[Article]:
        text = self.fetch_url(url)
        if not text:
            return []

        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            logger.warning(f"[HackerNoon] XML parse error for {feed_name}: {e}")
            return []

        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "content": "http://purl.org/rss/1.0/modules/content/",
        }

        articles: List[Article] = []
        items = root.findall(".//item")

        for item in items[: self.limit]:
            try:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if not title or not link:
                    continue

                # Deduplicate
                if link in seen:
                    continue
                seen.add(link)

                # Description + content
                description = (item.findtext("description") or "").strip()
                content_encoded = (item.findtext("content:encoded", namespaces=ns) or "").strip()
                full_html = content_encoded or description

                # Reading time
                reading_time = _estimate_reading_time(full_html)
                if reading_time < self.min_reading_time:
                    continue

                # Clean summary
                clean_text = re.sub(r"<[^>]+>", "", description)
                # Truncate at sentence boundary near 280 chars
                if len(clean_text) > 280:
                    idx = clean_text.rfind(".", 0, 300)
                    clean_text = clean_text[: idx + 1] if idx > 100 else clean_text[:280] + "…"
                summary_text = clean_text.strip()

                # Author
                author = (item.findtext("dc:creator", namespaces=ns) or "").strip()

                # Tags
                tags = []
                for cat in item.findall("category"):
                    if cat.text:
                        tags.append(cat.text.strip().lower())

                # Category
                category = _detect_category(tags, title)
                has_specific = category != "tech"

                # Quality
                quality = _compute_quality(reading_time, len(tags), has_specific)
                if quality < self.min_quality:
                    continue

                # Category filter
                if self.category_filter and category not in self.category_filter:
                    continue

                # Timestamp
                ts = None
                pub_date = item.findtext("pubDate")
                if pub_date:
                    try:
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # Build rich summary
                parts = []
                if author:
                    parts.append(f"✍️ {author}")
                parts.append(f"📖 {reading_time} min read")
                if summary_text:
                    parts.append(summary_text)
                summary = " · ".join(parts[:2]) + ("\n" + parts[2] if len(parts) > 2 else "")

                # Provenance tags
                prov_tags = [f"hackernoon:feed:{feed_name}"]
                prov_tags.extend(f"hackernoon:tag:{t}" for t in tags[:8])
                if category != "tech":
                    prov_tags.append(f"hackernoon:category:{category}")
                if author:
                    prov_tags.append(f"hackernoon:author:{author.lower().replace(' ', '-')}")

                articles.append(
                    Article(
                        title=title,
                        url=link,
                        source="Hacker Noon",
                        summary=summary,
                        timestamp=ts,
                        category=category,
                        tags=prov_tags,
                        author=author,
                        quality_score=quality,
                    )
                )
            except Exception as e:
                logger.debug(f"[HackerNoon] Skipping item: {e}")
                continue

        return articles
