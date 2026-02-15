"""EchoJS source — JavaScript/web dev news from echojs.com (no key needed)."""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

ECHOJS_API = "https://www.echojs.com/api/getnews/latest/0/30"


class EchoJSSource(BaseSource):
    """Fetch latest stories from EchoJS (JavaScript/web dev community)."""

    name = "echojs"

    def __init__(self, limit: int = 30):
        self.limit = limit

    def crawl(self) -> List[Article]:
        try:
            data = self.fetch_json(ECHOJS_API)
            if not data or "news" not in data:
                return []
        except Exception as e:
            logger.warning(f"[EchoJS] Failed to fetch: {e}")
            return []

        articles: List[Article] = []
        for item in data["news"][: self.limit]:
            try:
                title = item.get("title", "").strip()
                url = item.get("url", "").strip()
                if not title or not url:
                    continue

                # EchoJS uses atime (unix timestamp)
                ts = None
                atime = item.get("atime")
                if atime:
                    try:
                        ts = datetime.fromtimestamp(int(atime), tz=timezone.utc)
                    except (ValueError, TypeError, OSError):
                        pass

                up = item.get("up", 0)
                down = item.get("down", 0)
                score = int(up) - int(down)
                username = item.get("username", "")
                hn_id = item.get("id", "")
                discussion_url = f"https://www.echojs.com/news/{hn_id}" if hn_id else ""

                summary_parts = [f"Score: {score}"]
                if username:
                    summary_parts.append(f"By: {username}")
                if discussion_url:
                    summary_parts.append(f"Discussion: {discussion_url}")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"EchoJS (↑{score})",
                        summary=" | ".join(summary_parts),
                        timestamp=ts,
                        category="tech",
                        tags=["echojs:javascript", "echojs:webdev"],
                        author=username,
                        discussion_url=discussion_url,
                    )
                )
            except Exception as e:
                logger.debug(f"[EchoJS] Skipping item: {e}")
                continue

        logger.info(f"[EchoJS] Fetched {len(articles)} stories")
        return articles
