"""ProPublica source — independent, nonprofit investigative journalism.

ProPublica is a Pulitzer Prize-winning newsroom producing investigative
journalism in the public interest. Covers government accountability,
criminal justice, healthcare, education, technology, and environment.
"""
import logging
import re
from typing import List, Optional

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# ProPublica RSS feeds by section
PROPUBLICA_FEEDS = [
    {"url": "https://feeds.propublica.org/propublica/main", "section": "Top Stories", "category": "investigative"},
    {"url": "https://www.propublica.org/feeds/propublica/articles", "section": "Articles", "category": "investigative"},
]

CATEGORY_KEYWORDS = {
    "criminal_justice": ["police", "prison", "court", "judge", "sentencing", "incarceration", "bail", "criminal"],
    "healthcare": ["health", "hospital", "medicare", "medicaid", "insurance", "pharma", "drug", "patient", "doctor"],
    "education": ["school", "university", "student", "teacher", "education", "college", "campus"],
    "environment": ["climate", "pollution", "epa", "environmental", "water", "toxic", "emissions", "wildfire"],
    "tech": ["tech", "ai", "algorithm", "data", "privacy", "surveillance", "social media", "platform"],
    "government": ["congress", "senate", "federal", "government", "white house", "election", "vote", "lobby"],
    "finance": ["bank", "wall street", "sec", "fraud", "tax", "irs", "financial", "corporate"],
}


def _categorize(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "investigative"


class ProPublicaSource(BaseSource):
    """Crawl ProPublica's RSS feeds.

    Parameters
    ----------
    limit : int
        Max articles per feed. Default 20.
    categories : list of str or None
        Filter to specific categories. None = all.
    """

    name = "propublica"

    def __init__(self, limit: int = 20, categories: Optional[List[str]] = None):
        self.limit = limit
        self.categories = [c.lower() for c in categories] if categories else None

    def _parse_feed(self, feed_info: dict) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        default_category = feed_info["category"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for entry in parsed.entries[:self.limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            summary = entry.get("summary", "").strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

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
            category = _categorize(title, summary)

            if self.categories and category not in self.categories:
                continue

            tags = ["propublica", f"propublica:{section.lower().replace(' ', '_')}"]

            articles.append(Article(
                title=title,
                url=link,
                source=f"ProPublica ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
            ))

        return articles

    def crawl(self) -> List[Article]:
        all_articles = []
        for feed_info in PROPUBLICA_FEEDS:
            try:
                articles = self._parse_feed(feed_info)
                all_articles.extend(articles)
                logger.info(f"[ProPublica] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[ProPublica] Failed to parse {feed_info['section']}: {e}")

        logger.info(f"[ProPublica] Total: {len(all_articles)} articles")
        return all_articles
