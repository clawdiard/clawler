"""Slashdot source — fetches stories from Slashdot RSS feeds with quality scoring and smart categories."""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Available Slashdot section feeds
SLASHDOT_FEEDS: Dict[str, str] = {
    "main": "https://rss.slashdot.org/Slashdot/slashdotMain",
    "apple": "https://rss.slashdot.org/Slashdot/slashdotApple",
    "askslashdot": "https://rss.slashdot.org/Slashdot/slashdotAskSlashdot",
    "books": "https://rss.slashdot.org/Slashdot/slashdotBookReviews",
    "developers": "https://rss.slashdot.org/Slashdot/slashdotDevelopers",
    "hardware": "https://rss.slashdot.org/Slashdot/slashdotHardware",
    "interviews": "https://rss.slashdot.org/Slashdot/slashdotInterviews",
    "it": "https://rss.slashdot.org/Slashdot/slashdotIT",
    "linux": "https://rss.slashdot.org/Slashdot/slashdotLinux",
    "politics": "https://rss.slashdot.org/Slashdot/slashdotPolitics",
    "science": "https://rss.slashdot.org/Slashdot/slashdotScience",
    "yro": "https://rss.slashdot.org/Slashdot/slashdotYourRightsOnline",
}

# Section → default category mapping
SECTION_CATEGORY: Dict[str, str] = {
    "apple": "tech",
    "askslashdot": "tech",
    "books": "culture",
    "developers": "tech",
    "hardware": "tech",
    "interviews": "culture",
    "it": "tech",
    "linux": "tech",
    "politics": "world",
    "science": "science",
    "yro": "world",
}

# Keyword → category (specific categories checked first)
_SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "ai": ["ai", "artificial intelligence", "machine learning", "neural", "llm", "chatgpt",
           "openai", "deepmind", "gpt", "transformer", "deep learning", "copilot"],
    "security": ["security", "privacy", "hack", "breach", "vulnerability", "malware",
                 "ransomware", "exploit", "zero-day", "encryption", "backdoor", "phishing",
                 "cybersecurity", "nsa", "surveillance", "data leak", "infosec"],
    "crypto": ["bitcoin", "crypto", "blockchain", "ethereum", "nft", "defi", "web3",
               "mining", "token", "solana"],
    "science": ["science", "space", "physics", "climate", "nasa", "biology", "chemistry",
                "astronomy", "research", "study finds", "quantum", "cern", "mars",
                "telescope", "genome", "evolution", "fossil"],
    "health": ["health", "medical", "disease", "fda", "vaccine", "drug", "hospital",
               "cancer", "pandemic", "clinical trial", "mental health", "therapy"],
    "gaming": ["game", "gaming", "steam", "playstation", "xbox", "nintendo", "esport",
               "gpu", "console", "fps", "mmorpg"],
    "business": ["business", "economy", "startup", "acquisition", "ipo", "layoff",
                 "revenue", "earnings", "market", "stock", "venture", "merger",
                 "antitrust", "monopoly", "ftc", "regulation"],
    "design": ["design", "user interface", "user experience", "typography", "css", "frontend"],
    "world": ["politics", "government", "law", "court", "congress", "senate",
              "election", "supreme court", "legislation", "eu", "china", "russia",
              "ukraine", "regulation", "policy", "rights"],
    "culture": ["movie", "film", "book", "music", "entertainment", "tv", "show",
                "streaming", "netflix", "disney", "review"],
    "education": ["education", "university", "school", "student", "academic", "mooc",
                  "learning", "teaching"],
}

# Generic tech keywords (fallback)
_GENERIC_TECH = ["linux", "open source", "software", "programming", "developer",
                 "code", "internet", "browser", "server", "database", "api",
                 "apple", "google", "microsoft", "amazon", "meta", "hardware",
                 "chip", "processor", "memory", "network"]


def _strip_html(text: str) -> str:
    """Minimal HTML tag stripper."""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _extract_comment_count(entry) -> int:
    """Extract comment count from Slashdot RSS entry."""
    # slash:comments field
    comments_str = entry.get("slash_comments", "")
    if comments_str:
        try:
            return int(comments_str)
        except (ValueError, TypeError):
            pass
    # Sometimes in slash_hit_parade (format: replies,...)
    hit_parade = entry.get("slash_hit_parade", "")
    if hit_parade:
        try:
            return int(hit_parade.split(",")[0])
        except (ValueError, TypeError, IndexError):
            pass
    return 0


def _map_category(tags: List[str], title: str, section: str = "main") -> str:
    """Map Slashdot tags/title/section to clawler categories.

    Two-tier: specific categories first, then generic tech, then section default.
    """
    combined = " ".join(tags).lower() + " " + title.lower()

    # Check specific categories first
    for cat, keywords in _SPECIFIC_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return cat

    # Check generic tech
    if any(kw in combined for kw in _GENERIC_TECH):
        return "tech"

    # Fallback to section default
    return SECTION_CATEGORY.get(section, "tech")


def _quality_score(comment_count: int) -> float:
    """Compute quality score 0–1 based on comment count.

    Logarithmic scale: 0 comments ≈ 0.3, 10 ≈ 0.5, 50 ≈ 0.7, 200 ≈ 0.85, 500+ ≈ 0.95.
    Baseline 0.3 since Slashdot editorial curation already filters.
    """
    if comment_count <= 0:
        return 0.3
    return min(1.0, 0.3 + 0.25 * math.log10(1 + comment_count))


def _format_count(n: int) -> str:
    """Format number as human-readable (1.5K, 2.3M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class SlashdotSource(BaseSource):
    """Fetch stories from Slashdot via their public RSS feeds.

    Supports multiple section feeds, quality scoring, comment count extraction,
    and smart category detection.

    Args:
        sections: List of section names to fetch (default: ["main"]).
                  Use "all" to fetch all sections.
        limit: Max articles per section.
        global_limit: Max total articles (quality-sorted).
        min_comments: Skip stories with fewer comments.
        min_quality: Skip stories below this quality score (0–1).
        category_filter: Only return articles in these categories.
        section_filter: Only return articles from these sections (post-fetch).
    """

    name = "slashdot"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        limit: int = 25,
        global_limit: Optional[int] = None,
        min_comments: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        section_filter: Optional[List[str]] = None,
    ):
        self.sections = sections or ["main"]
        self.limit = limit
        self.global_limit = global_limit
        self.min_comments = min_comments
        self.min_quality = min_quality
        self.category_filter = category_filter
        self.section_filter = section_filter

    def crawl(self) -> List[Article]:
        try:
            import feedparser  # noqa: F401
        except ImportError:
            logger.warning("[Slashdot] feedparser not installed, skipping")
            return []

        sections = list(SLASHDOT_FEEDS.keys()) if "all" in self.sections else self.sections
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        for section in sections:
            feed_url = SLASHDOT_FEEDS.get(section)
            if not feed_url:
                logger.warning(f"[Slashdot] Unknown section: {section}")
                continue

            try:
                text = self.fetch_url(feed_url)
                if not text:
                    continue
            except Exception as e:
                logger.warning(f"[Slashdot] Failed to fetch {section}: {e}")
                continue

            import feedparser
            feed = feedparser.parse(text)

            for entry in feed.entries[: self.limit]:
                try:
                    title = entry.get("title", "").strip()
                    url = entry.get("link", "").strip()
                    if not title or not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Comment count
                    comment_count = _extract_comment_count(entry)
                    if comment_count < self.min_comments:
                        continue

                    # Quality score
                    quality = _quality_score(comment_count)
                    if quality < self.min_quality:
                        continue

                    # Parse summary
                    summary_raw = entry.get("summary", "")
                    summary = _strip_html(summary_raw)[:300]

                    # Author
                    author = entry.get("author", "") or entry.get("dc_creator", "")

                    # Timestamp
                    ts = None
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    if published:
                        try:
                            from calendar import timegm
                            ts = datetime.fromtimestamp(timegm(published), tz=timezone.utc)
                        except Exception:
                            pass

                    # Department
                    department = entry.get("slash_department", "")

                    # Build tags
                    tags: List[str] = [f"slashdot:section:{section}"]
                    for tag in entry.get("tags", []):
                        term = tag.get("term", "")
                        if term:
                            tags.append(f"slashdot:tag:{term}")
                    if department:
                        tags.append(f"slashdot:dept:{department}")
                    if comment_count > 0:
                        tags.append("slashdot:has-discussion")

                    # Category
                    category = _map_category(tags, title, section)
                    tags.append(f"slashdot:category:{category}")

                    # Category filter
                    if self.category_filter and category not in self.category_filter:
                        continue

                    # Section filter
                    if self.section_filter and section not in self.section_filter:
                        continue

                    # Enriched summary
                    parts = []
                    if department:
                        parts.append(f"🏷 {department}")
                    if comment_count > 0:
                        parts.append(f"💬 {_format_count(comment_count)} comments")
                    if parts:
                        prefix = " · ".join(parts)
                        summary = f"{prefix} — {summary}" if summary else prefix

                    # Comments URL
                    comments_url = entry.get("comments", url)

                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            source="Slashdot",
                            summary=summary,
                            timestamp=ts,
                            category=category,
                            tags=tags,
                            author=author,
                            discussion_url=comments_url if comments_url != url else "",
                            quality_score=quality,
                        )
                    )
                except Exception as e:
                    logger.debug(f"[Slashdot] Skipping entry: {e}")
                    continue

        # Sort by quality descending
        articles.sort(key=lambda a: (a.quality_score or 0), reverse=True)

        if self.global_limit:
            articles = articles[: self.global_limit]

        logger.info(f"[Slashdot] Fetched {len(articles)} stories from {len(sections)} section(s)")
        return articles
