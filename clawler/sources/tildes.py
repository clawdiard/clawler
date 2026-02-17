"""Tildes source — scrapes tildes.net topic listings (no API key needed)."""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

TILDES_URL = "https://tildes.net/"
TILDES_GROUP_URL = "https://tildes.net/~{group}"

# Sort options available on Tildes
VALID_SORTS = ("activity", "votes", "comments", "new")

# All known Tildes groups
DEFAULT_GROUPS = [
    "comp", "comp.ai", "comp.programming", "comp.hardware", "comp.os",
    "comp.os.linux", "science", "science.physics", "science.biology",
    "science.climate", "news", "news.politics", "news.international",
    "finance", "security", "privacy", "arts", "music", "books", "tv",
    "movies", "games", "misc", "misc.jobs", "enviro", "health",
    "food", "sports", "hobbies", "talk", "tildes",
]

# ── Keyword → category mapping (specific categories first) ──────────
_KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "ai", "artificial intelligence", "machine learning", "llm", "gpt",
        "chatgpt", "openai", "anthropic", "neural", "deep learning",
        "transformer", "diffusion", "copilot", "gemini", "claude",
    ],
    "security": [
        "security", "vulnerability", "exploit", "malware", "ransomware",
        "breach", "cve", "zero-day", "phishing", "encryption", "infosec",
        "backdoor", "firewall", "cybersecurity",
    ],
    "crypto": [
        "crypto", "bitcoin", "ethereum", "blockchain", "defi", "nft",
        "web3", "solana", "mining",
    ],
    "science": [
        "physics", "biology", "chemistry", "astronomy", "quantum",
        "climate", "genome", "crispr", "research", "study finds",
        "nasa", "telescope", "fusion", "particle",
    ],
    "health": [
        "health", "medical", "vaccine", "fda", "disease", "cancer",
        "mental health", "drug", "clinical trial", "hospital",
        "diagnosis", "therapy", "pandemic",
    ],
    "gaming": [
        "game", "gaming", "steam", "playstation", "xbox", "nintendo",
        "esports", "indie game", "rpg", "mmorpg",
    ],
    "design": [
        "design", "ux", "ui", "figma", "css", "typography", "accessibility",
        "a11y", "frontend", "web design",
    ],
    "business": [
        "startup", "ipo", "acquisition", "layoff", "revenue", "stock",
        "market", "economy", "inflation", "interest rate", "gdp",
        "trade", "tariff", "finance", "investment",
    ],
    "world": [
        "election", "war", "government", "congress", "parliament",
        "geopolitics", "sanctions", "diplomacy", "un ", "nato",
        "protest", "court", "legislation", "supreme court",
    ],
    "culture": [
        "book", "film", "movie", "music", "album", "tv show",
        "art", "literature", "comedy", "theater", "festival",
    ],
}

# ── Group → category mapping (fallback) ─────────────────────────────
_GROUP_CATEGORIES: Dict[str, str] = {
    "comp": "tech", "comp.ai": "ai", "comp.programming": "tech",
    "comp.hardware": "tech", "comp.os": "tech", "comp.os.linux": "tech",
    "science": "science", "science.physics": "science",
    "science.biology": "science", "science.climate": "science",
    "news": "world", "news.politics": "world", "news.international": "world",
    "finance": "business", "misc.jobs": "business",
    "security": "security", "privacy": "security",
    "arts": "culture", "music": "culture", "books": "culture",
    "tv": "culture", "movies": "culture",
    "games": "gaming",
    "enviro": "science", "health": "health", "food": "culture",
    "sports": "culture", "hobbies": "culture",
}


def _detect_category(title: str, group: str) -> str:
    """Two-tier category detection: keywords first, then group mapping."""
    title_lower = title.lower()
    for cat, keywords in _KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in title_lower:
                return cat
    return _GROUP_CATEGORIES.get(group.lower(), "tech")


def _quality_score(votes: int, comments: int) -> float:
    """Logarithmic quality score 0–1 based on engagement.
    
    Tildes baseline 0.2 (curated community), votes weighted 1x, comments 3x.
    50 engagement ≈ 0.6, 200+ ≈ 0.85.
    """
    engagement = votes + comments * 3
    if engagement <= 0:
        return 0.2
    raw = math.log10(1 + engagement) / math.log10(500)  # 500 engagement → 1.0
    return min(round(0.2 + 0.8 * raw, 3), 1.0)


def _human_count(n: int) -> str:
    """Format number as human-readable (1.5K, 2.3M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class TildesSource(BaseSource):
    """Fetch top topics from tildes.net via HTML scraping.
    
    Features:
    - Multi-group fetching with cross-group deduplication
    - Multiple sort modes: activity, votes, comments, new
    - Quality scoring (0–1) based on engagement
    - Keyword-based category detection with group fallback
    - Filters: min_votes, min_comments, min_quality, category_filter
    - Domain extraction for link posts
    - Global limit with quality-sorted output
    """

    name = "tildes"

    def __init__(
        self,
        limit: int = 25,
        groups: Optional[List[str]] = None,
        sort: str = "activity",
        min_votes: int = 0,
        min_comments: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_groups: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.limit = limit
        self.groups = groups  # None = front page only; list = per-group fetching
        self.sort = sort if sort in VALID_SORTS else "activity"
        self.min_votes = min_votes
        self.min_comments = min_comments
        self.min_quality = min_quality
        self.category_filter = set(category_filter) if category_filter else None
        self.exclude_groups = set(g.lower() for g in (exclude_groups or []))
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        if self.groups:
            for group in self.groups:
                if group.lower() in self.exclude_groups:
                    continue
                url = TILDES_GROUP_URL.format(group=group)
                if self.sort != "activity":
                    url += f"?order={self.sort}"
                try:
                    html = self.fetch_url(url)
                    if html:
                        articles = self._parse_topics(html, default_group=group)
                        for a in articles:
                            if a.url not in seen_urls:
                                seen_urls.add(a.url)
                                all_articles.append(a)
                except Exception as e:
                    logger.warning(f"[Tildes] Failed to fetch ~{group}: {e}")
        else:
            # Front page
            url = TILDES_URL
            if self.sort != "activity":
                url += f"?order={self.sort}"
            try:
                html = self.fetch_url(url)
                if html:
                    all_articles = self._parse_topics(html)
            except Exception as e:
                logger.warning(f"[Tildes] Failed to fetch front page: {e}")
                return []

        # Apply filters
        filtered = []
        for a in all_articles:
            if a.quality_score and a.quality_score < self.min_quality:
                continue
            if self.category_filter and a.category not in self.category_filter:
                continue
            filtered.append(a)

        # Sort by quality descending
        filtered.sort(key=lambda a: a.quality_score or 0, reverse=True)

        if self.global_limit:
            filtered = filtered[: self.global_limit]

        logger.info(f"[Tildes] Fetched {len(filtered)} topics (from {len(all_articles)} raw)")
        return filtered

    def _parse_topics(self, html: str, default_group: str = "") -> List[Article]:
        """Parse topic listings from Tildes HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        articles: List[Article] = []

        topics = soup.select("article.topic")
        for topic in topics[: self.limit]:
            try:
                # Title and URL
                title_el = topic.select_one("h1.topic-title a") or topic.select_one(".topic-title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")

                # External link or self-post
                link_el = topic.select_one("a.topic-info-source")
                source_domain = ""
                if link_el and link_el.get("href", "").startswith("http"):
                    url = link_el["href"]
                    # Extract domain
                    domain_match = re.search(r"https?://(?:www\.)?([^/]+)", url)
                    if domain_match:
                        source_domain = domain_match.group(1)
                elif url and not url.startswith("http"):
                    url = f"https://tildes.net{url}"

                if not title or not url:
                    continue

                # Discussion URL
                discussion_url = ""
                topic_link = topic.select_one("h1.topic-title a") or topic.select_one(".topic-title a")
                if topic_link:
                    href = topic_link.get("href", "")
                    if href.startswith("/"):
                        discussion_url = f"https://tildes.net{href}"
                    elif href.startswith("http"):
                        comment_link = topic.select_one("a.topic-info-comments")
                        if comment_link:
                            chref = comment_link.get("href", "")
                            discussion_url = f"https://tildes.net{chref}" if chref.startswith("/") else chref

                # Vote count
                votes = 0
                vote_el = topic.select_one(".topic-voting-votes")
                if vote_el:
                    try:
                        votes = int(vote_el.get_text(strip=True))
                    except (ValueError, TypeError):
                        pass

                # Apply min_votes filter early
                if votes < self.min_votes:
                    continue

                # Comment count
                comments = 0
                comment_el = topic.select_one("a.topic-info-comments") or topic.select_one(".topic-info-comments")
                if comment_el:
                    text = comment_el.get_text(strip=True)
                    m = re.search(r"(\d+)", text)
                    if m:
                        comments = int(m.group(1))

                # Apply min_comments filter early
                if comments < self.min_comments:
                    continue

                # Group/category
                group = default_group
                group_el = topic.select_one("a.topic-group") or topic.select_one(".topic-group")
                if group_el:
                    group = group_el.get_text(strip=True).lstrip("~")

                # Skip excluded groups
                if group.lower() in self.exclude_groups:
                    continue

                # Timestamp
                ts = None
                time_el = topic.select_one("time")
                if time_el and time_el.get("datetime"):
                    try:
                        ts = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, AttributeError):
                        pass

                # Tags
                tags = []
                topic_tags = []
                for tag_el in topic.select(".topic-tags a, .label-topic-tag"):
                    tag_text = tag_el.get_text(strip=True)
                    if tag_text:
                        topic_tags.append(tag_text)
                        tags.append(f"tildes:tag:{tag_text}")

                # Provenance tags
                if group:
                    tags.append(f"tildes:group:{group}")
                if source_domain and source_domain != "tildes.net":
                    tags.append(f"tildes:domain:{source_domain}")
                if discussion_url:
                    tags.append("tildes:has-discussion")

                # Category detection: keywords (title + tags) → group fallback
                combined_text = title + " " + " ".join(topic_tags)
                category = _detect_category(combined_text, group)
                tags.append(f"tildes:category:{category}")

                # Quality score
                score = _quality_score(votes, comments)

                # Build rich summary
                summary_parts = [f"⬆ {_human_count(votes)}"]
                summary_parts.append(f"💬 {_human_count(comments)}")
                if group:
                    summary_parts.append(f"📂 ~{group}")
                if source_domain and source_domain != "tildes.net":
                    summary_parts.append(f"🔗 {source_domain}")
                if topic_tags:
                    summary_parts.append(f"🏷 {', '.join(topic_tags[:5])}")
                if discussion_url:
                    summary_parts.append(f"Discussion: {discussion_url}")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Tildes (~{group})" if group else "Tildes",
                        summary=" | ".join(summary_parts),
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        discussion_url=discussion_url,
                        quality_score=score,
                    )
                )
            except Exception as e:
                logger.debug(f"[Tildes] Skipping topic: {e}")
                continue

        return articles
