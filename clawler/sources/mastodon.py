"""Mastodon/Fediverse trending source — uses public API (no key needed).

Fetches trending links, statuses, and hashtags from major Mastodon instances.
These represent content being widely shared across the fediverse.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
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

# Category keywords — expanded for better classification
_CATEGORY_KEYWORDS = {
    "ai": ("ai ", "artificial intelligence", "llm", "chatgpt", "openai", "machine learning",
            "deep learning", "neural", "gpt", "transformer", "copilot"),
    "tech": ("software", "programming", "code", "github", "open source", "linux",
             "developer", "tech", "startup", "app ", "rust ", "python", "javascript",
             "docker", "kubernetes", "api ", "cloud", "saas"),
    "science": ("climate", "space", "research", "study", "scientist", "physics",
                "biology", "nature", "nasa", "astronomy", "chemistry", "genome"),
    "security": ("security", "vulnerability", "exploit", "breach", "ransomware",
                 "malware", "cve", "infosec", "zero-day", "phishing", "encryption"),
    "business": ("market", "stock", "economy", "finance", "bank", "trade", "gdp",
                 "inflation", "crypto", "bitcoin", "venture", "ipo", "earnings"),
    "politics": ("election", "congress", "senate", "parliament", "government",
                 "legislation", "regulation", "supreme court", "policy", "democracy"),
    "health": ("health", "medical", "vaccine", "disease", "cancer", "therapy",
               "mental health", "fda", "clinical", "hospital"),
    "gaming": ("game", "gaming", "steam", "playstation", "xbox", "nintendo"),
    "design": ("design", "ux ", "ui ", "css", "figma", "typography", "accessibility"),
}


def _guess_category(title: str, description: str, provider: str = "") -> str:
    """Keyword-based category inference with priority ordering."""
    text = f"{title} {description} {provider}".lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "general"


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]


class MastodonSource(BaseSource):
    """Crawl trending links, statuses, and hashtags from Mastodon instances."""

    name = "mastodon"

    def __init__(
        self,
        instances: Optional[List[str]] = None,
        limit: int = 10,
        include_links: bool = True,
        include_statuses: bool = True,
        include_hashtags: bool = True,
        min_shares: int = 0,
        min_accounts: int = 0,
    ):
        self.instances = instances or DEFAULT_INSTANCES
        self.limit = limit
        self.include_links = include_links
        self.include_statuses = include_statuses
        self.include_hashtags = include_hashtags
        self.min_shares = min_shares
        self.min_accounts = min_accounts

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

            description = item.get("description", "").strip()
            provider = item.get("provider_name", "")
            total_shares, total_accounts = self._sum_history(item.get("history", []))

            if total_shares < self.min_shares or total_accounts < self.min_accounts:
                continue

            seen_urls.add(link_url)
            category = _guess_category(title, description, provider)

            summary_parts = []
            if description:
                summary_parts.append(description[:200])
            summary_parts.append(
                f"🐘 {total_shares} shares by {total_accounts} accounts on fediverse"
            )
            if provider:
                summary_parts.append(f"via {provider}")

            articles.append(Article(
                title=title,
                url=link_url,
                source=f"Mastodon ({instance})",
                summary=" | ".join(summary_parts),
                timestamp=datetime.now(tz=timezone.utc),
                category=category,
                tags=["fediverse", "trending", "link", f"instance:{instance}"],
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

            category = _guess_category(content, "", "")
            created = item.get("created_at", "")
            ts = datetime.now(tz=timezone.utc)
            if created:
                try:
                    ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            tags = ["fediverse", "trending", "status", f"instance:{instance}"]
            if acct:
                tags.append(f"author:{acct}")

            # Extract hashtags from the post
            post_tags = item.get("tags", [])
            for t in post_tags[:5]:
                tag_name = t.get("name", "")
                if tag_name:
                    tags.append(f"#{tag_name}")

            summary = (
                f"🐘 {reblogs} boosts, {favourites} favourites, {replies} replies"
                f"{f' | by {author}' if author else ''}"
            )

            articles.append(Article(
                title=title_text,
                url=status_url,
                source=f"Mastodon ({instance})",
                summary=summary,
                timestamp=ts,
                category=category,
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
            category = _guess_category(tag_name, "", "")

            articles.append(Article(
                title=f"#{tag_name} trending on {instance}",
                url=tag_url,
                source=f"Mastodon ({instance})",
                summary=f"🐘 #{tag_name} — {total_shares} uses by {total_accounts} accounts (last 3 days)",
                timestamp=datetime.now(tz=timezone.utc),
                category=category,
                tags=["fediverse", "trending", "hashtag", f"instance:{instance}", f"#{tag_name}"],
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
