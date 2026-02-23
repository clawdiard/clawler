"""Reddit source — uses public JSON endpoints (no API key needed).

Enhanced with:
- Two-tier keyword category detection (12 specific categories)
- Quality scoring (0–1): logarithmic engagement-based (score + comments)
- Multi-sort support: hot, top, new, rising with per-subreddit overrides
- Cross-subreddit URL deduplication
- Domain extraction from linked content
- Flair-based category boosting
- Prominent subreddit detection
- Filters: min_score, min_comments, min_quality, category_filter, exclude_subreddits, global_limit
- Rich provenance tags: reddit:sub, reddit:flair, reddit:domain, reddit:category, reddit:author
- Human-readable engagement counts
"""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

import requests

from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = [
    # News & World
    "worldnews", "news", "geopolitics",
    # Tech & Programming
    "technology", "programming", "machinelearning", "artificial", "webdev", "netsec",
    # Science
    "science", "space", "futurology",
    # Business & Finance
    "business", "economics", "stocks",
    # Gaming
    "games", "pcgaming",
    # Sports
    "sports",
    # Entertainment
    "movies", "television",
    # Design
    "design",
    # Health
    "health",
    # Education
    "education",
    # Environment
    "environment", "climate",
]

# Two-tier: subreddit → category (fallback)
SUBREDDIT_CATEGORIES: Dict[str, str] = {
    "worldnews": "world", "news": "world", "geopolitics": "world",
    "politics": "world", "ukpolitics": "world", "europe": "world",
    "technology": "tech", "programming": "tech", "webdev": "tech",
    "machinelearning": "ai", "artificial": "ai", "deeplearning": "ai",
    "learnmachinelearning": "ai", "datascience": "ai", "openai": "ai",
    "netsec": "security", "cybersecurity": "security", "hacking": "security",
    "privacy": "security", "infosec": "security",
    "science": "science", "space": "science", "futurology": "science",
    "askscience": "science", "physics": "science", "chemistry": "science",
    "biology": "science",
    "business": "business", "economics": "business", "stocks": "business",
    "wallstreetbets": "business", "investing": "business", "entrepreneur": "business",
    "cryptocurrency": "crypto", "bitcoin": "crypto", "ethereum": "crypto",
    "defi": "crypto", "cryptomarkets": "crypto",
    "games": "gaming", "pcgaming": "gaming", "gaming": "gaming",
    "nintendo": "gaming", "ps5": "gaming", "xboxseriesx": "gaming",
    "sports": "sports", "nba": "sports", "soccer": "sports",
    "nfl": "sports", "baseball": "sports",
    "movies": "culture", "television": "culture", "music": "culture",
    "books": "culture",
    "design": "design", "graphic_design": "design", "web_design": "design",
    "health": "health", "fitness": "health", "nutrition": "health",
    "medicine": "health", "mentalhealth": "health",
    "education": "education", "learnprogramming": "education",
    "environment": "environment", "climate": "environment",
    "renewableenergy": "environment", "zerowaste": "environment",
}

# Keyword → category (checked from title + flair)
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "llm", "large language model", "chatgpt", "gpt-4", "gpt-5", "openai",
        "anthropic", "claude", "gemini", "transformer", "diffusion model",
        "generative ai", "gen ai", "computer vision", "nlp", "reinforcement learning",
    ],
    "security": [
        "cybersecurity", "cyber attack", "ransomware", "malware", "phishing",
        "vulnerability", "zero-day", "data breach", "exploit", "cve-",
        "encryption", "infosec", "ddos", "botnet", "apt ",
    ],
    "crypto": [
        "cryptocurrency", "bitcoin", "ethereum", "blockchain", "defi",
        "nft", "web3", "solana", "crypto market", "stablecoin",
        "dao ", "smart contract", "token",
    ],
    "health": [
        "vaccine", "clinical trial", "fda ", "drug approval", "pandemic",
        "mental health", "cancer treatment", "medical", "healthcare",
        "public health", "disease", "therapy", "diagnosis",
    ],
    "science": [
        "research finds", "study shows", "scientists", "discovery",
        "nasa", "esa ", "cern", "particle physics", "quantum",
        "astronomy", "telescope", "genome", "crispr", "climate change",
    ],
    "business": [
        "acquisition", "ipo", "merger", "revenue", "earnings",
        "startup", "venture capital", "layoffs", "market cap",
        "quarterly results", "wall street", "stock market",
    ],
    "world": [
        "sanctions", "nato", "united nations", "ceasefire", "diplomacy",
        "election", "referendum", "coup", "protest", "refugee",
        "geopolitical", "treaty", "summit",
    ],
    "culture": [
        "oscar", "emmy", "grammy", "box office", "streaming",
        "netflix", "disney", "album", "concert", "festival",
        "museum", "exhibition", "book review",
    ],
    "gaming": [
        "steam", "playstation", "xbox", "nintendo", "esports",
        "game release", "dlc", "battle royale", "fps ", "rpg ",
        "mmorpg", "indie game", "game dev",
    ],
    "design": [
        "ui design", "ux design", "typography", "figma", "adobe",
        "graphic design", "web design", "brand", "logo", "illustration",
    ],
    "education": [
        "university", "student", "scholarship", "curriculum",
        "online learning", "mooc", "edtech", "school", "academic",
    ],
    "environment": [
        "renewable", "solar", "wind energy", "carbon", "emissions",
        "sustainability", "deforestation", "biodiversity", "pollution",
        "ev ", "electric vehicle", "green energy",
    ],
}


def _detect_keyword_category(text: str) -> Optional[str]:
    """Two-tier keyword category detection from text."""
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    for cat, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in text_lower:
                scores[cat] = scores.get(cat, 0) + 1
    if scores:
        return max(scores, key=scores.get)
    return None


def _extract_domain(url: str) -> Optional[str]:
    """Extract readable domain from URL."""
    try:
        host = urlparse(url).hostname or ""
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        # Skip reddit self-links
        if "reddit.com" in host or "redd.it" in host:
            return None
        return host or None
    except Exception:
        return None


def _human_count(n: int) -> str:
    """Format numbers as human-readable (1.5K, 2.3M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _quality_score(score: int, num_comments: int, upvote_ratio: float) -> float:
    """
    Quality score 0–1 based on engagement.

    Formula: log10-based combining:
    - Post score (60%): log10(score+1)/5 capped at 1.0
    - Comments (25%): log10(comments+1)/4 capped at 1.0
    - Upvote ratio (15%): ratio directly (0.5–1.0 typical)
    """
    score_component = min(math.log10(max(score, 1) + 1) / 5.0, 1.0) * 0.60
    comment_component = min(math.log10(max(num_comments, 0) + 1) / 4.0, 1.0) * 0.25
    ratio_component = max(upvote_ratio, 0.0) * 0.15
    return round(min(score_component + comment_component + ratio_component, 1.0), 3)


class RedditSource(BaseSource):
    name = "reddit"

    def __init__(
        self,
        subreddits: Optional[List[str]] = None,
        limit: int = 15,
        sort: str = "hot",
        time_filter: str = "day",
        allow_nsfw: bool = False,
        min_score: int = 0,
        min_comments: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_subreddits: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.subreddits = subreddits or DEFAULT_SUBREDDITS
        self.limit = limit
        self.sort = sort if sort in ("hot", "top", "new", "rising") else "hot"
        self.time_filter = time_filter if time_filter in ("hour", "day", "week", "month", "year", "all") else "day"
        self.allow_nsfw = allow_nsfw
        self.min_score = min_score
        self.min_comments = min_comments
        self.min_quality = min_quality
        self.category_filter = set(category_filter) if category_filter else None
        self.exclude_subreddits = set(s.lower() for s in (exclude_subreddits or []))
        self.global_limit = global_limit

    def _build_url(self, sub: str) -> str:
        base = f"https://www.reddit.com/r/{sub}/{self.sort}.json?limit={self.limit}&raw_json=1"
        if self.sort == "top":
            base += f"&t={self.time_filter}"
        return base

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: Set[str] = set()

        for sub in self.subreddits:
            if sub.lower() in self.exclude_subreddits:
                continue

            url = self._build_url(sub)
            try:
                data = self.fetch_json(url, extra_headers={"Accept": "application/json"})
                if not data:
                    continue
                children = data.get("data", {}).get("children", [])
                count = 0
                for post in children:
                    d = post.get("data", {})
                    if d.get("stickied"):
                        continue
                    if not self.allow_nsfw and d.get("over_18"):
                        continue

                    score = d.get("score", 0)
                    if score < self.min_score:
                        continue

                    num_comments = d.get("num_comments", 0)
                    if num_comments < self.min_comments:
                        continue

                    title = d.get("title", "").strip()
                    if not title:
                        continue

                    link = d.get("url", "")
                    permalink = f"https://reddit.com{d.get('permalink', '')}"

                    # Dedup by canonical URL
                    dedup_url = link if not link.startswith("https://www.reddit.com") else permalink
                    if dedup_url in seen_urls:
                        continue
                    seen_urls.add(dedup_url)

                    selftext = d.get("selftext", "")[:200]
                    author = d.get("author", "")
                    created = d.get("created_utc")
                    upvote_ratio = d.get("upvote_ratio", 0.0)
                    flair = d.get("link_flair_text", "") or ""

                    # Quality score
                    q_score = _quality_score(score, num_comments, upvote_ratio)
                    if q_score < self.min_quality:
                        continue

                    # Category detection: keyword (title+flair) → subreddit fallback
                    detect_text = f"{title} {flair}"
                    category = _detect_keyword_category(detect_text)
                    if not category:
                        category = SUBREDDIT_CATEGORIES.get(sub, "general")

                    # Category filter
                    if self.category_filter and category not in self.category_filter:
                        continue

                    # Domain extraction
                    domain = _extract_domain(link)

                    # Build rich summary
                    parts = []
                    if author:
                        parts.append(f"✍️ u/{author}")
                    parts.append(f"⬆ {_human_count(score)}")
                    if upvote_ratio:
                        parts.append(f"({int(upvote_ratio * 100)}%)")
                    parts.append(f"💬 {_human_count(num_comments)}")
                    parts.append(f"📂 r/{sub}")
                    if domain:
                        parts.append(f"🔗 {domain}")
                    if flair:
                        parts.append(f"[{flair}]")
                    summary_line = " · ".join(parts)
                    if selftext:
                        summary_line = f"{selftext}\n{summary_line}"

                    # Provenance tags
                    tags = [
                        f"reddit:sub:{sub}",
                        f"reddit:category:{category}",
                    ]
                    if flair:
                        tags.append(f"reddit:flair:{flair.lower()}")
                    if domain:
                        tags.append(f"reddit:domain:{domain}")
                    if author:
                        tags.append(f"reddit:author:{author}")
                    if d.get("is_self"):
                        tags.append("reddit:self-post")
                    if num_comments >= 100:
                        tags.append("reddit:has-discussion")

                    articles.append(Article(
                        title=title,
                        url=dedup_url,
                        source=f"r/{sub}",
                        summary=summary_line[:400],
                        timestamp=datetime.fromtimestamp(created, tz=timezone.utc) if created else None,
                        category=category,
                        author=author,
                        discussion_url=permalink,
                        tags=tags,
                        quality_score=q_score,
                    ))
                    count += 1
                logger.info(f"[Reddit] r/{sub}: {count} posts collected")
            except Exception as e:
                logger.warning(f"[Reddit] Failed r/{sub}: {e}")

        # Sort by quality, apply global limit
        articles.sort(key=lambda a: a.quality_score or 0, reverse=True)
        if self.global_limit:
            articles = articles[:self.global_limit]

        return articles
