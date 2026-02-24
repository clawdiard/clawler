"""The Hacker News source — cybersecurity news from thehackernews.com.

The Hacker News (not to be confused with Y Combinator's Hacker News) is one
of the most widely-read cybersecurity news outlets, covering data breaches,
vulnerabilities, malware, and security research.

Free RSS feed — no API key required.

Features: quality scoring based on topic specificity, keyword-based
sub-categorization (vulnerability, malware, breach, compliance, threat intel),
and prominent author tracking.
"""
import logging
import re
from typing import Dict, List, Set

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
_COMPLIANCE_KEYWORDS = frozenset({
    "compliance", "regulation", "gdpr", "hipaa", "pci", "nist",
    "audit", "framework", "policy", "standard",
})
_THREAT_INTEL_KEYWORDS = frozenset({
    "threat actor", "campaign", "espionage", "nation-state", "lazarus",
    "apt28", "apt29", "cozy bear", "fancy bear", "sandworm",
    "threat intelligence", "ioc", "indicators of compromise",
})

# Quality boost for specific, actionable content
_HIGH_VALUE_PATTERNS = [
    re.compile(r"CVE-\d{4}-\d+", re.IGNORECASE),  # Specific CVE references
    re.compile(r"critical|urgent|emergency|actively exploited", re.IGNORECASE),
]

# Prominent THN authors / contributors
PROMINENT_AUTHORS = frozenset({
    "ravie lakshmanan", "mohit kumar", "wang wei",
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
    if any(kw in text for kw in _COMPLIANCE_KEYWORDS):
        tags.append("compliance")
    if any(kw in text for kw in _THREAT_INTEL_KEYWORDS):
        tags.append("threat-intel")
    return tags


def _compute_quality(title: str, summary: str, author: str, security_tags: List[str]) -> float:
    """Compute quality score for a cybersecurity article.

    Base: 0.70 (THN is a respected cybersecurity source)
    Bonuses: specific CVEs, critical urgency, prominent authors, topic specificity.
    """
    quality = 0.70
    text = f"{title} {summary}"

    # Bonus for specific, actionable content (CVE references, urgency)
    for pattern in _HIGH_VALUE_PATTERNS:
        if pattern.search(text):
            quality += 0.04

    # Bonus for topic specificity (more tags = more detailed coverage)
    quality += min(0.10, len(security_tags) * 0.03)

    # Prominent author boost
    if author.lower() in PROMINENT_AUTHORS:
        quality += 0.03

    return min(1.0, quality)


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

            # Quality scoring
            quality = _compute_quality(title, summary, author, security_tags)

            articles.append(Article(
                title=title,
                url=link,
                source="The Hacker News",
                summary=summary,
                timestamp=ts,
                category="security",
                quality_score=quality,
                author=author,
                tags=tags,
            ))

        logger.info(f"[TheHackerNews] Fetched {len(articles)} articles")
        return articles
