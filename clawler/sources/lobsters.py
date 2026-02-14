"""Lobsters source — uses the free lobste.rs JSON API (no key needed)."""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

LOBSTERS_HOTTEST = "https://lobste.rs/hottest.json"
LOBSTERS_NEWEST = "https://lobste.rs/newest.json"


class LobstersSource(BaseSource):
    """Fetch hottest stories from lobste.rs."""

    name = "lobsters"

    def __init__(self, limit: int = 25, page: str = "hottest"):
        self.limit = limit
        self.url = LOBSTERS_NEWEST if page == "newest" else LOBSTERS_HOTTEST

    def crawl(self) -> List[Article]:
        try:
            data = self.fetch_json(self.url)
            if not data:
                return []
        except Exception as e:
            logger.warning(f"[Lobsters] Failed to fetch: {e}")
            return []

        articles: List[Article] = []
        for item in data[: self.limit]:
            try:
                title = item.get("title", "")
                url = item.get("url") or item.get("comments_url", "")
                if not title or not url:
                    continue

                score = item.get("score", 0)
                author = item.get("submitter_user", {})
                author_name = author.get("username", "") if isinstance(author, dict) else str(author)
                comment_count = item.get("comment_count", 0)
                comments_url = item.get("comments_url", "")
                tags = [t for t in item.get("tags", []) if isinstance(t, str)]

                # Parse timestamp (ISO 8601)
                ts = None
                created = item.get("created_at")
                if created:
                    try:
                        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, AttributeError):
                        pass

                # Map lobsters tags to categories
                category = _map_category(tags)

                summary_parts = [f"Score: {score}"]
                if author_name:
                    summary_parts.append(f"By: {author_name}")
                summary_parts.append(f"Comments: {comment_count}")
                if comments_url:
                    summary_parts.append(f"Discussion: {comments_url}")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Lobsters (↑{score})",
                        summary=" | ".join(summary_parts),
                        timestamp=ts,
                        category=category,
                        tags=[f"lobsters:{t}" for t in tags],
                    )
                )
            except Exception as e:
                logger.debug(f"[Lobsters] Skipping item: {e}")
                continue

        logger.info(f"[Lobsters] Fetched {len(articles)} stories")
        return articles


def _map_category(tags: List[str]) -> str:
    """Map lobste.rs tags to Clawler categories."""
    tag_set = set(t.lower() for t in tags)
    if tag_set & {"security", "privacy"}:
        return "security"
    if tag_set & {"science", "math"}:
        return "science"
    if tag_set & {"culture", "law", "person"}:
        return "culture"
    if tag_set & {"practices", "devops", "scaling"}:
        return "business"
    # Default: tech (lobste.rs is primarily a tech site)
    return "tech"
