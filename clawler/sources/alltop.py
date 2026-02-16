"""AllTop source — scrapes alltop.com topic pages for aggregated headlines.

AllTop curates top stories from popular publications across many categories.
No API key required — uses public HTML pages.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from html import unescape

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# AllTop topic slugs → clawler categories
TOPIC_CATEGORIES: Dict[str, str] = {
    "tech": "tech",
    "science": "science",
    "health": "health",
    "sports": "sports",
    "business": "business",
    "personal-finance": "finance",
    "politics": "politics",
    "food": "food",
    "travel": "travel",
    "music": "entertainment",
    "movies": "entertainment",
    "television": "entertainment",
    "gaming": "gaming",
    "photography": "design",
    "fitness": "health",
    "education": "education",
    "celebrity": "entertainment",
    "funny": "entertainment",
    "ecommerce": "business",
    "seo": "tech",
    "cryptocurrency": "crypto",
    "apple": "tech",
    "android": "tech",
    "linux": "tech",
    "autos": "automotive",
    "news": "general",
    "viral": "general",
    "homes": "lifestyle",
    "beauty": "lifestyle",
    "deals": "lifestyle",
    "lifehacks": "lifestyle",
    "religion": "culture",
    "formula-1": "sports",
}

DEFAULT_TOPICS = [
    "tech",
    "science",
    "business",
    "health",
    "sports",
    "news",
    "viral",
]

# Regex to extract stories from AllTop HTML
# Each story is an <a> with class "one-line-ellipsis" containing title text,
# href to the article, and a data-content popover with the description
STORY_RE = re.compile(
    r'<a\s+class="one-line-ellipsis"[^>]*'
    r'href="(https?://[^"]+)"[^>]*'
    r'data-content="([^"]*)"[^>]*>\s*'
    r'([^<]+?)\s*</a>',
    re.DOTALL,
)

# Extract source site name from popover: [...domain.com]
SOURCE_RE = re.compile(r'\[([^\]]+)\]')


class AllTopSource(BaseSource):
    """Fetch trending stories from AllTop topic pages."""

    name = "alltop"

    def __init__(
        self,
        topics: Optional[List[str]] = None,
        limit_per_topic: int = 10,
        max_total: int = 50,
    ):
        """
        Args:
            topics: List of AllTop topic slugs to scrape. Defaults to DEFAULT_TOPICS.
            limit_per_topic: Max stories to extract per topic page.
            max_total: Max total stories across all topics.
        """
        self.topics = topics or DEFAULT_TOPICS
        self.limit_per_topic = limit_per_topic
        self.max_total = max_total

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        for topic in self.topics:
            if len(articles) >= self.max_total:
                break

            url = f"https://alltop.com/{topic}"
            try:
                html = self.fetch_url(url)
                if not html:
                    continue
            except Exception as e:
                logger.warning(f"[AllTop] Failed to fetch {topic}: {e}")
                continue

            topic_articles = self._parse_topic(html, topic, seen_urls)
            articles.extend(topic_articles)

        logger.info(
            f"[AllTop] Fetched {len(articles)} stories from {len(self.topics)} topic(s)"
        )
        return articles[: self.max_total]

    def _parse_topic(
        self, html: str, topic: str, seen: Set[str]
    ) -> List[Article]:
        results: List[Article] = []
        category = TOPIC_CATEGORIES.get(topic, "general")

        matches = STORY_RE.findall(html)

        for article_url, data_content, title_raw in matches:
            if len(results) >= self.limit_per_topic:
                break

            article_url = article_url.strip()
            if not article_url or article_url in seen:
                continue
            seen.add(article_url)

            title = unescape(title_raw).strip()
            if not title:
                continue

            # Extract description from data-content popover
            summary = _extract_description(data_content)

            # Extract source publication from popover [...domain.com]
            source_match = SOURCE_RE.search(data_content)
            source_name = source_match.group(1) if source_match else "AllTop"

            results.append(
                Article(
                    title=title,
                    url=article_url,
                    source=f"AllTop/{topic} ({source_name})",
                    summary=summary,
                    timestamp=datetime.now(timezone.utc),
                    category=category,
                    tags=[f"alltop:{topic}"],
                )
            )

        return results


def _extract_description(data_content: str) -> str:
    """Extract readable description from AllTop's data-content popover HTML."""
    if not data_content:
        return ""
    text = unescape(data_content)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove [...domain.com] source markers
    text = SOURCE_RE.sub("", text)
    # Remove "[ Read Article ]" text
    text = re.sub(r"\[\s*Read Article\s*\]", "", text)
    # Clean whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to reasonable length
    if len(text) > 300:
        text = text[:297] + "..."
    return text
