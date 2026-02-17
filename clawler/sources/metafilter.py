"""MetaFilter source — community-curated links with quality scoring and smart categories.

MetaFilter (est. 1999) is a community weblog with highly curated, thoughtful
discussions. It includes several sub-sites:

- MetaFilter (main): "the best of the web" — general interest links
- Ask MetaFilter: Q&A community
- FanFare: TV, movies, books, podcasts discussion
- Projects: member side-projects and creations
- Music: member-created music

All sub-sites have public RSS/Atom feeds, no API key required.
"""
import logging
import math
import re
from calendar import timegm
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Available MetaFilter feeds
METAFILTER_FEEDS: Dict[str, str] = {
    "main": "https://feeds.metafilter.com/main.rss",
    "ask": "https://feeds.metafilter.com/ask.rss",
    "fanfare": "https://feeds.metafilter.com/fanfare.rss",
    "projects": "https://feeds.metafilter.com/projects.rss",
    "music": "https://feeds.metafilter.com/music.rss",
    "metatalk": "https://feeds.metafilter.com/metatalk.rss",
}

# Sub-site → default category mapping
SUBSITE_CATEGORY: Dict[str, str] = {
    "main": "tech",
    "ask": "culture",
    "fanfare": "culture",
    "projects": "tech",
    "music": "culture",
    "metatalk": "culture",
}

# Keyword → category (specific categories checked first)
_SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "ai": ["ai", "artificial intelligence", "machine learning", "neural", "llm",
           "chatgpt", "openai", "gpt", "deep learning", "copilot", "generative"],
    "security": ["security", "privacy", "hack", "breach", "vulnerability", "malware",
                 "ransomware", "exploit", "encryption", "surveillance", "cybersecurity",
                 "phishing", "nsa", "infosec"],
    "crypto": ["bitcoin", "crypto", "blockchain", "ethereum", "nft", "defi", "web3"],
    "science": ["science", "space", "physics", "climate", "nasa", "biology", "chemistry",
                "astronomy", "research", "quantum", "mars", "telescope", "genome",
                "evolution", "fossil", "neuroscience", "ecology"],
    "health": ["health", "medical", "disease", "fda", "vaccine", "drug", "hospital",
               "cancer", "pandemic", "mental health", "therapy", "diagnosis"],
    "gaming": ["game", "gaming", "steam", "playstation", "xbox", "nintendo", "esport",
               "video game", "tabletop", "board game", "rpg"],
    "business": ["business", "economy", "startup", "acquisition", "ipo", "layoff",
                 "revenue", "market", "stock", "venture", "merger", "antitrust"],
    "design": ["design", "typography", "css", "frontend", "illustration", "graphic",
               "architecture", "ux", "ui"],
    "world": ["politics", "government", "law", "court", "congress", "senate",
              "election", "supreme court", "legislation", "eu", "china", "russia",
              "ukraine", "war", "democracy", "rights", "justice", "immigration"],
    "culture": ["movie", "film", "book", "music", "entertainment", "tv", "show",
                "streaming", "art", "literature", "poetry", "museum", "history",
                "photography", "comic", "anime", "manga"],
    "education": ["education", "university", "school", "student", "academic",
                  "learning", "teaching", "library", "scholarship"],
    "environment": ["environment", "climate change", "sustainability", "renewable",
                    "pollution", "conservation", "biodiversity", "ocean", "forest"],
}

# Generic tech keywords (fallback)
_GENERIC_TECH = ["linux", "open source", "software", "programming", "developer",
                 "code", "internet", "browser", "server", "database", "api",
                 "apple", "google", "microsoft", "amazon", "hardware", "algorithm",
                 "computer", "web", "app", "tech"]


def _strip_html(text: str) -> str:
    """Minimal HTML tag stripper."""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"&[a-zA-Z]+;", " ", clean)
    clean = re.sub(r"&#\d+;", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _extract_comment_count(entry) -> int:
    """Extract comment count from RSS entry.

    MetaFilter includes comment counts in slash:comments or in the
    description text (e.g., "[N comments]").
    """
    # slash:comments field (standard slash namespace)
    comments_str = entry.get("slash_comments", "")
    if comments_str:
        try:
            return int(comments_str)
        except (ValueError, TypeError):
            pass

    # Try to find in summary text: "N comments" or "N favorites"
    summary = entry.get("summary", "") or entry.get("description", "")
    m = re.search(r"(\d+)\s+comments?", summary, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass

    return 0


def _extract_favorites(entry) -> int:
    """Extract favorite count from entry if available."""
    summary = entry.get("summary", "") or entry.get("description", "")
    m = re.search(r"(\d+)\s+favorites?", summary, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 0


def _extract_domain(entry) -> str:
    """Extract the primary linked domain from entry content."""
    content = entry.get("summary", "") or entry.get("description", "")
    # Find first non-metafilter link
    urls = re.findall(r'href=["\']([^"\']+)["\']', content)
    for u in urls:
        try:
            parsed = urlparse(u)
            host = parsed.netloc.lower()
            if host and "metafilter" not in host:
                # Strip www.
                if host.startswith("www."):
                    host = host[4:]
                return host
        except Exception:
            continue
    return ""


def _map_category(title: str, summary: str, subsite: str = "main") -> str:
    """Map title + summary to a category.

    Two-tier: specific categories first, then generic tech, then subsite default.
    """
    combined = (title + " " + summary).lower()

    # Check specific categories first (word boundary matching)
    for cat, keywords in _SPECIFIC_KEYWORDS.items():
        for kw in keywords:
            # Use word boundary check to avoid substring false positives
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, combined):
                return cat

    # Check generic tech (word boundary)
    for kw in _GENERIC_TECH:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, combined):
            return "tech"

    # Fallback to subsite default
    return SUBSITE_CATEGORY.get(subsite, "culture")


def _quality_score(comment_count: int, favorites: int = 0) -> float:
    """Compute quality score 0–1 based on engagement.

    Logarithmic scale with baseline 0.4 (MetaFilter has strong editorial
    curation via the $5 membership wall).
    Comments weighted 70%, favorites 30%.
    """
    engagement = comment_count + favorites * 0.5
    if engagement <= 0:
        return 0.4
    return min(1.0, 0.4 + 0.22 * math.log10(1 + engagement))


def _format_count(n: int) -> str:
    """Format number as human-readable."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class MetaFilterSource(BaseSource):
    """Fetch posts from MetaFilter via public RSS feeds.

    Supports multiple sub-sites, quality scoring, comment/favorite extraction,
    domain extraction, and smart category detection.

    Args:
        subsites: List of sub-site names to fetch (default: ["main", "ask"]).
                  Use "all" to fetch all sub-sites.
        limit: Max articles per sub-site feed.
        global_limit: Max total articles (quality-sorted).
        min_comments: Skip posts with fewer comments.
        min_quality: Skip posts below this quality score (0–1).
        category_filter: Only return articles in these categories.
        subsite_filter: Only return articles from these sub-sites (post-fetch).
    """

    name = "metafilter"

    def __init__(
        self,
        subsites: Optional[List[str]] = None,
        limit: int = 25,
        global_limit: Optional[int] = None,
        min_comments: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        subsite_filter: Optional[List[str]] = None,
    ):
        self.subsites = subsites or ["main", "ask"]
        self.limit = limit
        self.global_limit = global_limit
        self.min_comments = min_comments
        self.min_quality = min_quality
        self.category_filter = category_filter
        self.subsite_filter = subsite_filter

    def crawl(self) -> List[Article]:
        try:
            import feedparser  # noqa: F401
        except ImportError:
            logger.warning("[MetaFilter] feedparser not installed, skipping")
            return []

        subsites = list(METAFILTER_FEEDS.keys()) if "all" in self.subsites else self.subsites
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        for subsite in subsites:
            feed_url = METAFILTER_FEEDS.get(subsite)
            if not feed_url:
                logger.warning(f"[MetaFilter] Unknown sub-site: {subsite}")
                continue

            try:
                text = self.fetch_url(feed_url)
                if not text:
                    continue
            except Exception as e:
                logger.warning(f"[MetaFilter] Failed to fetch {subsite}: {e}")
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

                    # Comment & favorite counts
                    comment_count = _extract_comment_count(entry)
                    favorites = _extract_favorites(entry)
                    if comment_count < self.min_comments:
                        continue

                    # Quality score
                    quality = _quality_score(comment_count, favorites)
                    if quality < self.min_quality:
                        continue

                    # Parse summary
                    summary_raw = entry.get("summary", "") or entry.get("description", "")
                    summary_clean = _strip_html(summary_raw)[:300]

                    # Category detection
                    category = _map_category(title, summary_clean, subsite)

                    # Category filter
                    if self.category_filter and category not in self.category_filter:
                        continue

                    # Subsite filter
                    if self.subsite_filter and subsite not in self.subsite_filter:
                        continue

                    # Author
                    author = entry.get("author", "") or entry.get("dc_creator", "")

                    # Timestamp
                    ts = None
                    published = entry.get("published_parsed") or entry.get("updated_parsed")
                    if published:
                        try:
                            ts = datetime.fromtimestamp(timegm(published), tz=timezone.utc)
                        except Exception:
                            pass

                    # Domain extraction
                    domain = _extract_domain(entry)

                    # Build tags
                    tags: List[str] = [f"metafilter:subsite:{subsite}"]
                    for tag in entry.get("tags", []):
                        term = tag.get("term", "")
                        if term:
                            tags.append(f"metafilter:tag:{term.lower()}")
                    if domain:
                        tags.append(f"metafilter:domain:{domain}")
                    if comment_count > 0:
                        tags.append("metafilter:has-discussion")
                    if author:
                        tags.append(f"metafilter:author:{author}")
                    tags.append(f"metafilter:category:{category}")

                    # Enriched summary
                    parts = []
                    if subsite != "main":
                        label = {"ask": "Ask MeFi", "fanfare": "FanFare",
                                 "projects": "Projects", "music": "Music",
                                 "metatalk": "MetaTalk"}.get(subsite, subsite.title())
                        parts.append(f"📂 {label}")
                    if domain:
                        parts.append(f"🔗 {domain}")
                    if comment_count > 0:
                        parts.append(f"💬 {_format_count(comment_count)}")
                    if favorites > 0:
                        parts.append(f"⭐ {_format_count(favorites)}")
                    if author:
                        parts.append(f"✍️ {author}")
                    if parts:
                        prefix = " · ".join(parts)
                        summary_clean = f"{prefix} — {summary_clean}" if summary_clean else prefix

                    # Sub-site display name
                    source_name = {
                        "main": "MetaFilter",
                        "ask": "Ask MetaFilter",
                        "fanfare": "MetaFilter FanFare",
                        "projects": "MetaFilter Projects",
                        "music": "MetaFilter Music",
                        "metatalk": "MetaTalk",
                    }.get(subsite, "MetaFilter")

                    articles.append(
                        Article(
                            title=title,
                            url=url,
                            source=source_name,
                            summary=summary_clean,
                            timestamp=ts,
                            category=category,
                            tags=tags,
                            author=author,
                            discussion_url=url,  # MeFi posts ARE the discussion
                            quality_score=quality,
                        )
                    )
                except Exception as e:
                    logger.debug(f"[MetaFilter] Skipping entry: {e}")
                    continue

        # Sort by quality descending
        articles.sort(key=lambda a: (a.quality_score or 0), reverse=True)

        if self.global_limit:
            articles = articles[: self.global_limit]

        logger.info(f"[MetaFilter] Fetched {len(articles)} posts from {len(subsites)} sub-site(s)")
        return articles
