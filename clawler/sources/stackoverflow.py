"""Stack Overflow / Stack Exchange source for Clawler.

Enhanced with:
- Multi-site support (Stack Overflow + other SE sites like serverfault, superuser, etc.)
- Quality scoring based on engagement (score, answers, views)
- Keyword-based category detection (ai, security, science, etc.)
- min_score / min_views / min_answers filtering
- Accepted-answer-only mode
- Tag-based provenance tags (so:tag:<name>, so:site:<site>)
- Cross-site deduplication
- Human-readable counts in summaries
"""
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from clawler.sources.base import BaseSource
from clawler.models import Article

logger = logging.getLogger(__name__)

# Stack Exchange API — no key required (quota: 300 requests/day per IP)
SE_API = "https://api.stackexchange.com/2.3/questions"

DEFAULT_SITES: Dict[str, str] = {
    "stackoverflow": "tech",
    "serverfault": "tech",
    "superuser": "tech",
    "security": "security",
    "datascience": "ai",
    "stats": "ai",
    "gamedev": "gaming",
    "ux": "design",
    "money": "business",
}

# Keyword → category mappings (specific beats generic)
KEYWORD_CATEGORIES = {
    "ai": ["machine-learning", "deep-learning", "neural-network", "tensorflow", "pytorch",
           "nlp", "computer-vision", "gpt", "llm", "openai", "chatgpt", "langchain",
           "transformers", "scikit-learn", "keras", "artificial-intelligence", "data-science"],
    "security": ["security", "encryption", "authentication", "oauth", "jwt", "xss", "csrf",
                 "sql-injection", "vulnerability", "penetration-testing", "cryptography",
                 "ssl", "tls", "firewall", "malware", "ransomware"],
    "crypto": ["blockchain", "ethereum", "solidity", "web3", "smart-contracts", "bitcoin",
               "cryptocurrency", "nft", "defi"],
    "science": ["physics", "chemistry", "biology", "astronomy", "mathematics", "statistics",
                "quantum", "genome", "climate"],
    "health": ["health", "medical", "bioinformatics", "healthcare"],
    "gaming": ["unity", "unreal-engine", "game-development", "gamedev", "godot", "pygame"],
    "design": ["css", "ui-design", "ux", "figma", "responsive-design", "accessibility",
               "svg", "animation", "tailwind-css", "bootstrap"],
    "business": ["project-management", "agile", "scrum", "jira", "enterprise", "saas",
                 "startup", "marketing"],
}


def _human_count(n: int) -> str:
    """Format number as human-readable (1.2K, 3.4M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _decode_entities(text: str) -> str:
    """Decode common HTML entities in Stack Exchange API responses."""
    return (text.replace("&#39;", "'").replace("&amp;", "&")
            .replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">"))


def _detect_category(tags: List[str], site_default: str = "tech") -> str:
    """Two-tier category detection: specific keywords first, then site default."""
    tags_lower = {t.lower() for t in tags}
    for category, keywords in KEYWORD_CATEGORIES.items():
        if tags_lower & set(keywords):
            return category
    return site_default


def _quality_score(score: int, answer_count: int, view_count: int,
                   is_answered: bool) -> float:
    """Compute 0–1 quality score from engagement metrics.

    Uses logarithmic scale combining:
    - vote score (weight 0.4)
    - view count (weight 0.3)
    - answer engagement (weight 0.2)
    - answered bonus (weight 0.1)
    """
    # Logarithmic normalization: log10(1+x) / log10(1+max_expected)
    score_norm = min(math.log10(1 + max(score, 0)) / math.log10(1001), 1.0)  # 1000 = exceptional
    view_norm = min(math.log10(1 + view_count) / math.log10(1_000_001), 1.0)  # 1M = exceptional
    answer_norm = min(math.log10(1 + answer_count) / math.log10(51), 1.0)  # 50 = exceptional
    answered_bonus = 1.0 if is_answered else 0.0

    return round(score_norm * 0.4 + view_norm * 0.3 + answer_norm * 0.2 + answered_bonus * 0.1, 3)


class StackOverflowSource(BaseSource):
    """Fetch hot questions from Stack Overflow and other Stack Exchange sites.

    Params:
        sites: dict of {site_name: default_category} to crawl (default: DEFAULT_SITES)
        sort: API sort mode — hot, activity, votes, creation (default: hot)
        min_score: minimum vote score to include (default: 0)
        min_views: minimum view count to include (default: 0)
        min_answers: minimum answer count (default: 0)
        accepted_only: only include questions with accepted answers (default: False)
        tag_filter: only include questions with at least one of these tags (default: None)
        category_filter: only include questions matching these categories (default: None)
        min_quality: minimum quality_score threshold (default: 0.0)
        limit: max results per site (default: 30)
        global_limit: max total results across all sites (default: None)
    """

    name = "Stack Overflow"
    source_type = "api"

    def __init__(self, sites: Optional[Dict[str, str]] = None, sort: str = "hot",
                 min_score: int = 0, min_views: int = 0, min_answers: int = 0,
                 accepted_only: bool = False, tag_filter: Optional[List[str]] = None,
                 category_filter: Optional[List[str]] = None,
                 min_quality: float = 0.0, limit: int = 30,
                 global_limit: Optional[int] = None):
        self.sites = sites or DEFAULT_SITES
        self.sort = sort
        self.min_score = min_score
        self.min_views = min_views
        self.min_answers = min_answers
        self.accepted_only = accepted_only
        self.tag_filter = set(t.lower() for t in tag_filter) if tag_filter else None
        self.category_filter = set(category_filter) if category_filter else None
        self.min_quality = min_quality
        self.limit = limit
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen_urls: Set[str] = set()

        for site, site_default_cat in self.sites.items():
            url = (f"{SE_API}?order=desc&sort={self.sort}&site={site}"
                   f"&pagesize={self.limit}&filter=!nNPvSNdWme")
            data = self.fetch_json(url)
            if not data or "items" not in data:
                logger.warning(f"[StackOverflow] No data from {site}")
                continue

            for item in data["items"]:
                title = _decode_entities(item.get("title", ""))
                link = item.get("link", "")
                if not title or not link:
                    continue

                # Dedup across sites
                if link in seen_urls:
                    continue
                seen_urls.add(link)

                score = item.get("score", 0)
                answer_count = item.get("answer_count", 0)
                view_count = item.get("view_count", 0)
                is_answered = item.get("is_answered", False)
                tags = item.get("tags", [])[:8]

                # Apply filters
                if score < self.min_score:
                    continue
                if view_count < self.min_views:
                    continue
                if answer_count < self.min_answers:
                    continue
                if self.accepted_only and not item.get("accepted_answer_id"):
                    continue
                if self.tag_filter and not (set(t.lower() for t in tags) & self.tag_filter):
                    continue

                # Category detection
                category = _detect_category(tags, site_default_cat)
                if self.category_filter and category not in self.category_filter:
                    continue

                # Quality score
                q_score = _quality_score(score, answer_count, view_count, is_answered)
                if q_score < self.min_quality:
                    continue

                # Timestamp
                created = item.get("creation_date")
                ts = datetime.fromtimestamp(created, tz=timezone.utc) if created else None

                # Summary
                parts = []
                if tags:
                    parts.append(f"Tags: {', '.join(tags)}")
                status = "✅" if is_answered else "❓"
                parts.append(f"{status} Score: {_human_count(score)} | "
                             f"Answers: {answer_count} | Views: {_human_count(view_count)}")
                summary = " — ".join(parts)

                # Author
                owner = item.get("owner", {})
                author = _decode_entities(owner.get("display_name", ""))

                # Provenance tags
                prov_tags = [f"so:site:{site}"]
                prov_tags.extend(f"so:tag:{t}" for t in tags)
                prov_tags.append(f"so:category:{category}")
                if is_answered:
                    prov_tags.append("so:answered")

                articles_entry = Article(
                    title=title,
                    url=link,
                    source=f"Stack Overflow" if site == "stackoverflow" else f"SE/{site}",
                    summary=summary,
                    timestamp=ts,
                    category=category,
                    tags=prov_tags,
                    author=author,
                    quality_score=q_score,
                )
                all_articles.append(articles_entry)

            logger.info(f"[StackOverflow] Fetched from {site}: {len([a for a in all_articles if f'so:site:{site}' in a.tags])} questions")

        # Sort by quality score descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        # Apply global limit
        if self.global_limit and len(all_articles) > self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[StackOverflow] Total: {len(all_articles)} questions across {len(self.sites)} sites")
        return all_articles
