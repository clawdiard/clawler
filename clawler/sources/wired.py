"""Wired source — fetches articles from wired.com RSS feeds.

Covers technology, science, culture, business, and gear with
high-quality long-form journalism.

Enhanced features:
- 10 section feeds (was 6): added backchannel, ideas, reviews, politics
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on section prominence × position decay + author reputation
- Prominent journalist detection (20+ Wired journalists) with reputation boost
- Cross-section URL deduplication
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries with ✍️ author · 📰 section · description
- Provenance tags: wired:section, wired:category, wired:author, wired:prominent-author, wired:tag
"""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

WIRED_FEEDS: Dict[str, Dict] = {
    "main":       {"url": "https://www.wired.com/feed/rss", "category": "tech", "prominence": 0.55},
    "science":    {"url": "https://www.wired.com/feed/category/science/latest/rss", "category": "science", "prominence": 0.50},
    "security":   {"url": "https://www.wired.com/feed/category/security/latest/rss", "category": "security", "prominence": 0.52},
    "business":   {"url": "https://www.wired.com/feed/category/business/latest/rss", "category": "business", "prominence": 0.45},
    "culture":    {"url": "https://www.wired.com/feed/category/culture/latest/rss", "category": "culture", "prominence": 0.40},
    "gear":       {"url": "https://www.wired.com/feed/category/gear/latest/rss", "category": "tech", "prominence": 0.38},
    "backchannel": {"url": "https://www.wired.com/feed/category/backchannel/latest/rss", "category": "tech", "prominence": 0.50},
    "ideas":      {"url": "https://www.wired.com/feed/category/ideas/latest/rss", "category": "culture", "prominence": 0.45},
    "reviews":    {"url": "https://www.wired.com/feed/category/reviews/latest/rss", "category": "tech", "prominence": 0.35},
    "politics":   {"url": "https://www.wired.com/feed/category/politics/latest/rss", "category": "world", "prominence": 0.45},
}

# Prominent Wired journalists — get quality boost
PROMINENT_AUTHORS: Set[str] = {
    "andy greenberg", "lily hay newman", "brian barrett", "matt burgess",
    "steven levy", "lauren goode", "kate knibbs", "will knight",
    "aarian marshall", "paresh dave", "garrett m. graff", "virginia heffernan",
    "angela watercutter", "julian chokkattu", "eric ravenscraft", "scott gilbertson",
    "michael calore", "adrienne so", "khari johnson", "tom simonite",
    "emily mullin", "megan molteni", "kim zetter", "nicole kobie",
}

AUTHOR_BOOST = 0.08

# Categories that get a quality boost when detected via keywords
BOOSTED_CATEGORIES: Set[str] = {"ai", "security", "crypto", "environment"}

# Two-tier keyword detection: specific categories checked before section fallback
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": ["artificial intelligence", " ai ", "machine learning", "deep learning",
           "neural network", "llm", "large language model", "chatgpt", "gpt-4",
           "openai", "anthropic", "generative ai", "transformer", "diffusion model",
           "computer vision", "nlp", "reinforcement learning", "autonomous"],
    "security": ["cybersecurity", "hacker", "malware", "ransomware", "phishing",
                 "vulnerability", "zero-day", "exploit", "data breach", "encryption",
                 "surveillance", "privacy", "spyware", "infosec", "backdoor",
                 "nation-state", "apt ", "credential"],
    "crypto": ["cryptocurrency", "bitcoin", "ethereum", "blockchain", "defi",
               "web3", "nft", "token", "crypto ", "stablecoin", "dao "],
    "health": ["health", "medical", "disease", "vaccine", "clinical",
               "patient", "therapy", "drug ", "fda ", "mental health",
               "pandemic", "crispr", "biotech", "genomic"],
    "science": ["climate", "physics", "biology", "chemistry", "nasa",
                "space", "quantum", "genome", "evolution", "neuroscience",
                "astronomy", "fossil", "mars ", "telescope"],
    "business": ["startup", "acquisition", "ipo ", "revenue", "valuation",
                 "venture capital", "layoff", "merger", "antitrust", "regulation"],
    "world": ["geopolitic", "election", "government", "war ", "conflict",
              "diplomat", "sanction", "refugee", "united nations", "treaty"],
    "culture": ["movie", "film ", "tv show", "streaming", "music ",
                "album", "book ", "novel", "art ", "museum"],
    "education": ["education", "university", "student", "campus", "school",
                  "academic", "professor", "curriculum"],
    "environment": ["climate change", "carbon", "emissions", "renewable",
                    "sustainability", "pollution", "wildfire", "drought",
                    "deforestation", "biodiversity"],
    "gaming": ["video game", "gaming", "playstation", "xbox", "nintendo",
               "esport", "steam ", "game developer"],
    "design": ["ux ", "ui ", "user experience", "interface design",
               "typography", "graphic design", "industrial design"],
}


def _detect_category(title: str, description: str, rss_tags: List[str], section_fallback: str) -> str:
    """Two-tier: check specific keywords first, then fall back to section category."""
    text = f"{title} {description} {' '.join(rss_tags)}".lower()

    matches: Dict[str, int] = {}
    for cat, keywords in KEYWORD_CATEGORIES.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > 0:
            matches[cat] = count

    if matches:
        # Prefer boosted categories when tied
        best = max(matches, key=lambda c: (matches[c], c in BOOSTED_CATEGORIES))
        return best

    return section_fallback


def _compute_quality(position: int, section_prominence: float,
                     is_prominent_author: bool, category: str) -> float:
    """Quality score 0–1: prominence × position decay + author boost + category boost."""
    position_factor = 1.0 / (1.0 + 0.08 * position)
    score = section_prominence * position_factor

    if is_prominent_author:
        score += AUTHOR_BOOST

    if category in BOOSTED_CATEGORIES:
        score += 0.03

    return min(max(score, 0.0), 1.0)


class WiredSource(BaseSource):
    """Fetch articles from Wired RSS feeds."""

    name = "wired"

    def __init__(
        self,
        limit: int = 20,
        feeds: Optional[List[str]] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = set(category_filter) if category_filter else None
        self.exclude_sections = set(exclude_sections) if exclude_sections else set()
        self.global_limit = global_limit

        if feeds is not None:
            self._feeds = [f for f in feeds if f in WIRED_FEEDS]
        else:
            self._feeds = ["main", "science", "security", "business", "culture", "gear"]

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        active_feeds = [f for f in self._feeds if f not in self.exclude_sections]

        for section in active_feeds:
            feed_info = WIRED_FEEDS[section]
            try:
                xml_text = self.fetch_url(feed_info["url"])
                if not xml_text:
                    continue
                parsed = self._parse_feed(xml_text, section, feed_info, seen_urls)
                articles.extend(parsed)
            except Exception as e:
                logger.warning(f"[Wired] Failed to fetch {section}: {e}")

        # Filter by quality
        if self.min_quality > 0:
            articles = [a for a in articles if (a.quality_score or 0) >= self.min_quality]

        # Filter by category
        if self.category_filter:
            articles = [a for a in articles if a.category in self.category_filter]

        # Sort by quality descending
        articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Apply global limit
        if self.global_limit:
            articles = articles[:self.global_limit]

        logger.info(f"[Wired] Fetched {len(articles)} articles from {len(active_feeds)} section(s)")
        return articles

    def _parse_feed(self, xml_text: str, section: str, feed_info: dict,
                    seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[Wired] XML parse error for {section}: {e}")
            return articles

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        items = root.findall(".//item")

        for position, item in enumerate(items[:self.limit]):
            try:
                article = self._parse_item(item, section, feed_info, seen, ns, position)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[Wired] Skipping item in {section}: {e}")

        return articles

    def _parse_item(self, item, section: str, feed_info: dict,
                    seen: Set[str], ns: dict, position: int) -> Optional[Article]:
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

        # Description
        description = ""
        if desc_el is not None and desc_el.text:
            description = re.sub(r"<[^>]+>", "", desc_el.text).strip()

        # Author
        author = ""
        if author_el is not None and author_el.text:
            author = author_el.text.strip()

        is_prominent = author.lower() in PROMINENT_AUTHORS

        # RSS tags
        rss_tags: List[str] = []
        for cat_el in item.findall("category"):
            if cat_el.text:
                rss_tags.append(cat_el.text.strip().lower())

        # Category detection
        section_fallback = feed_info["category"]
        category = _detect_category(title, description, rss_tags, section_fallback)

        # Quality score
        prominence = feed_info["prominence"]
        quality = _compute_quality(position, prominence, is_prominent, category)

        # Build summary
        summary_parts = []
        if author:
            summary_parts.append(f"✍️ {author}")
        summary_parts.append(f"📰 {section.title()}")
        if description:
            desc_truncated = description[:280]
            if len(description) > 280:
                # Truncate at sentence boundary
                last_period = desc_truncated.rfind(".")
                if last_period > 100:
                    desc_truncated = desc_truncated[:last_period + 1]
                else:
                    desc_truncated = desc_truncated[:277] + "..."
            summary_parts.append(desc_truncated)
        summary = " · ".join(summary_parts[:2])
        if len(summary_parts) > 2:
            summary = summary + "\n" + summary_parts[2]

        # Tags
        tags = [f"wired:section:{section}"]
        tags.append(f"wired:category:{category}")
        if author:
            tags.append(f"wired:author:{author.lower()}")
        if is_prominent:
            tags.append("wired:prominent-author")
        for rt in rss_tags:
            tags.append(f"wired:tag:{rt}")

        ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)

        return Article(
            title=title,
            url=url,
            source=f"Wired ({section})",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=quality,
        )


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
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
