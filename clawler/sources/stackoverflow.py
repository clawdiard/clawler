"""Stack Overflow Hot Questions source for Clawler."""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.sources.base import BaseSource
from clawler.models import Article

logger = logging.getLogger(__name__)

# Stack Exchange API — no key required (quota: 300 requests/day per IP)
HOT_QUESTIONS_URL = "https://api.stackexchange.com/2.3/questions?order=desc&sort=hot&site=stackoverflow&pagesize=30&filter=!nNPvSNdWme"


def _decode_entities(text: str) -> str:
    """Decode common HTML entities in Stack Exchange API responses."""
    return (text.replace("&#39;", "'").replace("&amp;", "&")
            .replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">"))


class StackOverflowSource(BaseSource):
    """Fetch hot questions from Stack Overflow."""

    name = "Stack Overflow"
    source_type = "api"

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        data = self.fetch_json(HOT_QUESTIONS_URL)
        if not data or "items" not in data:
            return articles

        for item in data["items"]:
            title = _decode_entities(item.get("title", ""))
            link = item.get("link", "")
            if not title or not link:
                continue

            created = item.get("creation_date")
            ts = datetime.fromtimestamp(created, tz=timezone.utc) if created else None

            tags = item.get("tags", [])[:5]
            score = item.get("score", 0)
            answer_count = item.get("answer_count", 0)
            view_count = item.get("view_count", 0)

            summary_parts = []
            if tags:
                summary_parts.append(f"Tags: {', '.join(tags)}")
            summary_parts.append(f"Score: {score} | Answers: {answer_count} | Views: {view_count}")
            summary = " — ".join(summary_parts)

            owner = item.get("owner", {})
            author = owner.get("display_name", "")

            articles.append(Article(
                title=title,
                url=link,
                source="Stack Overflow",
                summary=summary,
                timestamp=ts,
                category="tech",
                tags=tags,
                author=author,
            ))

        logger.info(f"[StackOverflow] Fetched {len(articles)} hot questions")
        return articles
