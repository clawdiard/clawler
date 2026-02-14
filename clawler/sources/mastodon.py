"""Mastodon/Fediverse trending source — uses public API (no key needed).

Fetches trending links from major Mastodon instances. These are stories
that are being widely shared across the fediverse.
"""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Large, well-known instances with public trending APIs
DEFAULT_INSTANCES = [
    "mastodon.social",
    "mastodon.online",
    "fosstodon.org",
    "hachyderm.io",
]


class MastodonSource(BaseSource):
    """Crawl trending links from Mastodon instances."""

    name = "mastodon"

    def __init__(self, instances: List[str] = None, limit: int = 10):
        self.instances = instances or DEFAULT_INSTANCES
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        for instance in self.instances:
            url = f"https://{instance}/api/v1/trends/links?limit={self.limit}"
            data = self.fetch_json(url)
            if not data or not isinstance(data, list):
                logger.info(f"[Mastodon] No trending data from {instance}")
                continue

            for item in data:
                link_url = item.get("url", "").strip()
                if not link_url or link_url in seen_urls:
                    continue
                seen_urls.add(link_url)

                title = item.get("title", "").strip()
                if not title:
                    continue

                description = item.get("description", "").strip()
                provider = item.get("provider_name", instance)
                history = item.get("history", [])

                # Sum recent shares from history buckets
                total_shares = 0
                total_accounts = 0
                for bucket in history[:3]:  # last 3 days
                    total_shares += int(bucket.get("uses", 0))
                    total_accounts += int(bucket.get("accounts", 0))

                # Determine category from provider/content heuristics
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
                    timestamp=datetime.now(tz=timezone.utc),  # trending = recent
                    category=category,
                    tags=["fediverse", "trending"],
                ))

        logger.info(f"[Mastodon] Collected {len(articles)} trending links")
        return articles


def _guess_category(title: str, description: str, provider: str) -> str:
    """Simple keyword-based category inference."""
    text = f"{title} {description} {provider}".lower()
    if any(kw in text for kw in ("ai ", "software", "programming", "code", "github",
                                   "open source", "linux", "developer", "tech", "cyber",
                                   "hack", "startup", "app ")):
        return "tech"
    if any(kw in text for kw in ("climate", "space", "research", "study", "scientist",
                                   "physics", "biology", "nature")):
        return "science"
    if any(kw in text for kw in ("market", "stock", "economy", "finance", "bank",
                                   "trade", "gdp", "inflation")):
        return "business"
    if any(kw in text for kw in ("security", "vulnerability", "exploit", "breach",
                                   "ransomware", "malware", "cve")):
        return "security"
    return "general"
