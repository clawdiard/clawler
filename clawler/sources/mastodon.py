"""Mastodon/Fediverse trending source — uses public API (no key needed).

Fetches trending links, statuses, and hashtags from major Mastodon instances.
These represent content being widely shared across the fediverse.

v10.3: quality scoring, instance specialization, language filter, engagement formatting,
       specific-over-generic categories, hashtag-based category boost, global limit.
"""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Large, well-known instances with public trending APIs
DEFAULT_INSTANCES = [
    "mastodon.social",
    "mastodon.online",
    "fosstodon.org",
    "hachyderm.io",
    "infosec.exchange",
    "mas.to",
]

# Instance → default category bias (content on these instances leans this way)
INSTANCE_CATEGORY_BIAS: Dict[str, str] = {
    "fosstodon.org": "tech",
    "hachyderm.io": "tech",
    "infosec.exchange": "security",
}

# Specific categories checked FIRST (higher priority)
_SPECIFIC_CATEGORY_KEYWORDS = {
    "ai": ("ai ", "artificial intelligence", "llm", "chatgpt", "openai", "machine learning",
            "machinelearning", "deep learning", "deeplearning", "neural", "gpt", "transformer",
            "copilot", "anthropic", "gemini", "claude", "stable diffusion", "midjourney",
            "diffusion model"),
    "security": ("security", "vulnerability", "exploit", "breach", "ransomware",
                 "malware", "cve", "infosec", "zero-day", "phishing", "encryption",
                 "cybersecurity", "pentest", "threat", "firewall", "siem"),
    "crypto": ("crypto", "bitcoin", "ethereum", "blockchain", "defi", "nft",
               "web3", "solidity", "dao", "token"),
    "science": ("climate", "space", "research", "study", "scientist", "physics",
                "biology", "nature", "nasa", "astronomy", "chemistry", "genome",
                "neuroscience", "quantum", "crispr", "paleontology"),
    "health": ("health", "medical", "vaccine", "disease", "cancer", "therapy",
               "mental health", "fda", "clinical", "hospital", "pandemic",
               "diagnosis", "pharmaceutical"),
    "business": ("market", "stock", "economy", "finance", "bank", "trade", "gdp",
                 "inflation", "venture", "ipo", "earnings", "recession", "startup"),
    "gaming": ("game", "gaming", "steam", "playstation", "xbox", "nintendo",
               "esports", "indie game", "unity", "unreal engine"),
    "design": ("design", "ux ", "ui ", "css", "figma", "typography",
               "accessibility", "a11y", "wcag"),
    "world": ("election", "congress", "senate", "parliament", "government",
              "legislation", "regulation", "supreme court", "policy", "democracy",
              "war ", "geopolitics", "diplomacy", "united nations", "nato"),
    "culture": ("film", "movie", "music", "book ", "novel", "art ", "museum",
                "theater", "theatre", "podcast", "album"),
}

# Generic fallback categories checked SECOND
_GENERIC_CATEGORY_KEYWORDS = {
    "tech": ("software", "programming", "code", "github", "open source", "linux",
             "developer", "tech", "app ", "rust ", "python", "javascript",
             "docker", "kubernetes", "api ", "cloud", "saas", "foss"),
}


def _guess_category(title: str, description: str, provider: str = "",
                    hashtags: Optional[List[str]] = None,
                    instance: str = "") -> str:
    """Two-tier keyword category detection: specific first, generic second, instance bias fallback."""
    text = f"{title} {description} {provider}".lower()
    if hashtags:
        text += " " + " ".join(h.lower() for h in hashtags)

    # Specific categories first
    for category, keywords in _SPECIFIC_CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category

    # Generic fallback
    for category, keywords in _GENERIC_CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category

    # Instance bias
    if instance in INSTANCE_CATEGORY_BIAS:
        return INSTANCE_CATEGORY_BIAS[instance]

    return "general"


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]


def _format_count(n: int) -> str:
    """Human-readable count: 1.5K, 2.3M."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _quality_score_links(shares: int, accounts: int) -> float:
    """Quality score 0–1 for trending links based on shares and accounts.
    Uses log scale: 10 shares ≈ 0.3, 100 ≈ 0.6, 1000 ≈ 0.9."""
    if shares <= 0:
        return 0.0
    raw = math.log10(max(shares, 1)) + (accounts / max(shares, 1)) * 0.2
    return round(min(max(raw / 3.5, 0.0), 1.0), 2)


def _quality_score_status(reblogs: int, favourites: int, replies: int) -> float:
    """Quality score 0–1 for statuses based on engagement.
    Weighted: reblogs×3 + favourites + replies×2."""
    engagement = reblogs * 3 + favourites + replies * 2
    if engagement <= 0:
        return 0.0
    raw = math.log10(max(engagement, 1))
    return round(min(max(raw / 4.0, 0.0), 1.0), 2)


def _quality_score_hashtag(shares: int, accounts: int) -> float:
    """Quality score 0–1 for hashtags based on usage breadth."""
    if accounts <= 0:
        return 0.0
    raw = math.log10(max(accounts, 1)) + (shares / max(accounts, 1)) * 0.1
    return round(min(max(raw / 3.0, 0.0), 1.0), 2)


class MastodonSource(BaseSource):
    """Crawl trending links, statuses, and hashtags from Mastodon instances."""

    name = "mastodon"

    def __init__(
        self,
        instances: Optional[List[str]] = None,
        limit: int = 10,
        global_limit: int = 0,
        include_links: bool = True,
        include_statuses: bool = True,
        include_hashtags: bool = True,
        min_shares: int = 0,
        min_accounts: int = 0,
        min_quality: float = 0.0,
        language: Optional[str] = None,
        category_filter: Optional[List[str]] = None,
    ):
        self.instances = instances or DEFAULT_INSTANCES
        self.limit = limit
        self.global_limit = global_limit
        self.include_links = include_links
        self.include_statuses = include_statuses
        self.include_hashtags = include_hashtags
        self.min_shares = min_shares
        self.min_accounts = min_accounts
        self.min_quality = min_quality
        self.language = language
        self.category_filter = category_filter

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        for instance in self.instances:
            if self.include_links:
                articles.extend(self._crawl_links(instance, seen_urls))
            if self.include_statuses:
                articles.extend(self._crawl_statuses(instance, seen_urls))
            if self.include_hashtags:
                articles.extend(self._crawl_hashtags(instance, seen_urls))

        # Filter by category if requested
        if self.category_filter:
            articles = [a for a in articles if a.category in self.category_filter]

        # Filter by minimum quality
        if self.min_quality > 0:
            articles = [a for a in articles if a.quality_score >= self.min_quality]

        # Sort by quality descending
        articles.sort(key=lambda a: a.quality_score, reverse=True)

        # Apply global limit
        if self.global_limit > 0:
            articles = articles[:self.global_limit]

        logger.info(f"[Mastodon] Collected {len(articles)} items from {len(self.instances)} instances")
        return articles

    def _crawl_links(self, instance: str, seen_urls: set) -> List[Article]:
        """Fetch trending links (external articles being shared)."""
        articles = []
        url = f"https://{instance}/api/v1/trends/links?limit={self.limit}"
        data = self.fetch_json(url)
        if not data or not isinstance(data, list):
            logger.info(f"[Mastodon] No trending links from {instance}")
            return articles

        for item in data:
            link_url = item.get("url", "").strip()
            if not link_url or link_url in seen_urls:
                continue

            title = item.get("title", "").strip()
            if not title:
                continue

            # Language filter
            lang = item.get("language", "")
            if self.language and lang and lang != self.language:
                continue

            description = item.get("description", "").strip()
            provider = item.get("provider_name", "")
            total_shares, total_accounts = self._sum_history(item.get("history", []))

            if total_shares < self.min_shares or total_accounts < self.min_accounts:
                continue

            seen_urls.add(link_url)
            category = _guess_category(title, description, provider, instance=instance)
            score = _quality_score_links(total_shares, total_accounts)

            summary_parts = []
            if description:
                summary_parts.append(description[:200])
            summary_parts.append(
                f"🐘 {_format_count(total_shares)} shares by {_format_count(total_accounts)} accounts"
            )
            if provider:
                summary_parts.append(f"via {provider}")

            tags = [
                "fediverse", "trending", "link",
                f"mastodon:instance:{instance}",
                f"mastodon:category:{category}",
            ]
            if provider:
                tags.append(f"mastodon:provider:{provider}")

            articles.append(Article(
                title=title,
                url=link_url,
                source=f"Mastodon ({instance})",
                summary=" | ".join(summary_parts),
                timestamp=datetime.now(tz=timezone.utc),
                category=category,
                quality_score=score,
                tags=tags,
            ))
        return articles

    def _crawl_statuses(self, instance: str, seen_urls: set) -> List[Article]:
        """Fetch trending statuses (popular posts on the instance)."""
        articles = []
        url = f"https://{instance}/api/v1/trends/statuses?limit={self.limit}"
        data = self.fetch_json(url)
        if not data or not isinstance(data, list):
            logger.info(f"[Mastodon] No trending statuses from {instance}")
            return articles

        for item in data:
            status_url = item.get("url", "").strip()
            if not status_url or status_url in seen_urls:
                continue

            # Language filter
            lang = item.get("language", "")
            if self.language and lang and lang != self.language:
                continue

            content = _strip_html(item.get("content", ""))
            if not content:
                continue

            seen_urls.add(status_url)

            account = item.get("account", {})
            author = account.get("display_name", "") or account.get("username", "")
            acct = account.get("acct", "")

            # Engagement metrics
            reblogs = item.get("reblogs_count", 0)
            favourites = item.get("favourites_count", 0)
            replies = item.get("replies_count", 0)

            # Title: first line or truncated content
            title_text = content.split("\n")[0][:120]
            if len(title_text) < len(content):
                title_text += "…"

            # Extract hashtags from post tags
            post_tags = item.get("tags", [])
            hashtag_names = [t.get("name", "") for t in post_tags[:10] if t.get("name")]

            category = _guess_category(content, "", "", hashtags=hashtag_names, instance=instance)
            score = _quality_score_status(reblogs, favourites, replies)

            created = item.get("created_at", "")
            ts = datetime.now(tz=timezone.utc)
            if created:
                try:
                    ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            tags = [
                "fediverse", "trending", "status",
                f"mastodon:instance:{instance}",
                f"mastodon:category:{category}",
            ]
            if acct:
                tags.append(f"mastodon:author:{acct}")
            for hn in hashtag_names[:5]:
                tags.append(f"mastodon:hashtag:{hn}")

            summary = (
                f"🐘 {_format_count(reblogs)} boosts, {_format_count(favourites)} favs, "
                f"{_format_count(replies)} replies"
                f"{f' | by {author}' if author else ''}"
            )

            articles.append(Article(
                title=title_text,
                url=status_url,
                source=f"Mastodon ({instance})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=score,
                tags=tags,
            ))
        return articles

    def _crawl_hashtags(self, instance: str, seen_urls: set) -> List[Article]:
        """Fetch trending hashtags and create summary articles for each."""
        articles = []
        url = f"https://{instance}/api/v1/trends/tags?limit={self.limit}"
        data = self.fetch_json(url)
        if not data or not isinstance(data, list):
            logger.info(f"[Mastodon] No trending hashtags from {instance}")
            return articles

        for item in data:
            tag_name = item.get("name", "").strip()
            if not tag_name:
                continue

            tag_url = item.get("url", f"https://{instance}/tags/{tag_name}")
            if tag_url in seen_urls:
                continue

            total_shares, total_accounts = self._sum_history(item.get("history", []))
            if total_shares < self.min_shares or total_accounts < self.min_accounts:
                continue

            seen_urls.add(tag_url)
            category = _guess_category(tag_name, "", "", hashtags=[tag_name], instance=instance)
            score = _quality_score_hashtag(total_shares, total_accounts)

            tags = [
                "fediverse", "trending", "hashtag",
                f"mastodon:instance:{instance}",
                f"mastodon:hashtag:{tag_name}",
                f"mastodon:category:{category}",
            ]

            articles.append(Article(
                title=f"#{tag_name} trending on {instance}",
                url=tag_url,
                source=f"Mastodon ({instance})",
                summary=f"🐘 #{tag_name} — {_format_count(total_shares)} uses by {_format_count(total_accounts)} accounts (last 3 days)",
                timestamp=datetime.now(tz=timezone.utc),
                category=category,
                quality_score=score,
                tags=tags,
            ))
        return articles

    @staticmethod
    def _sum_history(history: list) -> tuple:
        """Sum shares and accounts from history buckets (last 3 days)."""
        total_shares = 0
        total_accounts = 0
        for bucket in history[:3]:
            total_shares += int(bucket.get("uses", 0))
            total_accounts += int(bucket.get("accounts", 0))
        return total_shares, total_accounts
