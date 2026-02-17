"""The Hacker News source — cybersecurity news from thehackernews.com.

The Hacker News (not to be confused with Y Combinator's Hacker News) is one
of the most widely-read cybersecurity news outlets, covering data breaches,
vulnerabilities, malware, and security research.

Free RSS feed — no API key required.
"""
import logging
import re
from typing import List

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

FEED_URL = "https://feeds.feedburner.com/TheHackersNews"

# Keywords for sub-categorization
_VULN_KEYWORDS = frozenset({
    "vulnerability", "cve", "zero-day", "0-day", "exploit", "patch",
    "rce", "xss", "sql injection", "buffer overflow", "flaw",
})
_MALWARE_KEYWORDS = frozenset({
    "malware", "ransomware", "trojan", "botnet", "spyware", "backdoor",
    "worm", "rootkit", "phishing", "apt",
})
_BREACH_KEYWORDS = frozenset({
    "breach", "leak", "exposed", "stolen", "hack", "hacked", "compromised",
    "data leak", "credentials",
})


def _classify_security_topic(title: str, summary: str) -> List[str]:
    """Return security-specific tags based on title/summary keywords."""
    text = f"{title} {summary}".lower()
    tags = []
    if any(kw in text for kw in _VULN_KEYWORDS):
        tags.append("vulnerability")
    if any(kw in text for kw in _MALWARE_KEYWORDS):
        tags.append("malware")
    if any(kw in text for kw in _BREACH_KEYWORDS):
        tags.append("breach")
    return tags


class TheHackerNewsSource(BaseSource):
    """Crawl The Hacker News RSS feed for cybersecurity articles.

    Parameters
    ----------
    limit : int
        Max articles to return. Default 25.
    """

    name = "thehackernews"

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        content = self.fetch_url(FEED_URL)
        if not content:
            logger.warning("[TheHackerNews] Empty response from feed")
            return []

        parsed = feedparser.parse(content)
        articles = []

        for entry in parsed.entries[:self.limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            # Clean summary
            summary = entry.get("summary", "").strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 400:
                    summary = summary[:397] + "..."

            # Parse timestamp
            ts = None
            for date_field in ("published", "updated"):
                raw = entry.get(date_field)
                if raw:
                    try:
                        ts = dateparser.parse(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            author = entry.get("author", "")

            # Build tags
            security_tags = _classify_security_topic(title, summary)
            tags = ["thehackernews", "cybersecurity"] + security_tags

            # Extract feed-provided categories/tags
            for tag_entry in entry.get("tags", []):
                term = tag_entry.get("term", "").strip().lower()
                if term and term not in tags:
                    tags.append(term)

            articles.append(Article(
                title=title,
                url=link,
                source="The Hacker News",
                summary=summary,
                timestamp=ts,
                category="security",
                author=author,
                tags=tags,
            ))

        logger.info(f"[TheHackerNews] Fetched {len(articles)} articles")
        return articles
