"""Lemmy source — fetches trending posts from Lemmy instances via public API (no auth needed)."""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Popular Lemmy instances with diverse communities
LEMMY_INSTANCES = [
    {"url": "https://lemmy.world", "name": "lemmy.world"},
    {"url": "https://lemmy.ml", "name": "lemmy.ml"},
    {"url": "https://programming.dev", "name": "programming.dev"},
]


class LemmySource(BaseSource):
    """Fetch trending posts from Lemmy instances via their public API."""

    name = "lemmy"

    def __init__(self, limit: int = 15):
        self.limit = limit

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        for instance in LEMMY_INSTANCES:
            try:
                articles = self._fetch_instance(instance)
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[Lemmy] Failed to fetch {instance['name']}: {e}")
        logger.info(f"[Lemmy] Fetched {len(all_articles)} posts across {len(LEMMY_INSTANCES)} instances")
        return all_articles

    def _fetch_instance(self, instance: dict) -> List[Article]:
        """Fetch hot posts from a single Lemmy instance."""
        api_url = f"{instance['url']}/api/v3/post/list?sort=Hot&limit={self.limit}&type_=All"
        data = self.fetch_json(api_url)
        if not data or "posts" not in data:
            return []

        articles: List[Article] = []
        for post_view in data["posts"][: self.limit]:
            try:
                post = post_view.get("post", {})
                community = post_view.get("community", {})
                counts = post_view.get("counts", {})

                title = post.get("name", "").strip()
                if not title:
                    continue

                # Use external link if available, otherwise the Lemmy post URL
                url = post.get("url") or f"{instance['url']}/post/{post.get('id', '')}"
                if not url:
                    continue

                # Discussion URL is always the Lemmy post page
                discussion_url = f"{instance['url']}/post/{post.get('id', '')}"

                # Timestamp
                ts = None
                published = post.get("published")
                if published:
                    try:
                        # Lemmy uses ISO 8601 format
                        clean = published.replace("Z", "+00:00")
                        ts = datetime.fromisoformat(clean)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, AttributeError):
                        pass

                # Metadata
                score = counts.get("score", 0)
                comments = counts.get("comments", 0)
                community_name = community.get("name", "")
                community_title = community.get("title", community_name)

                # Author
                creator = post_view.get("creator", {})
                author = creator.get("name", "")

                # Tags
                tags = []
                if community_name:
                    tags.append(f"lemmy:{community_name}")

                category = _map_category(community_name)

                summary_parts = [f"Score: {score}", f"Comments: {comments}"]
                if community_title:
                    summary_parts.append(f"Community: {community_title}")
                if discussion_url:
                    summary_parts.append(f"Discussion: {discussion_url}")

                source_label = f"Lemmy ({instance['name']})"

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=source_label,
                        summary=" | ".join(summary_parts),
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=author,
                        discussion_url=discussion_url,
                    )
                )
            except Exception as e:
                logger.debug(f"[Lemmy] Skipping post: {e}")
                continue

        return articles


def _map_category(community: str) -> str:
    """Map Lemmy community names to Clawler categories."""
    c = community.lower()
    if c in ("technology", "programming", "linux", "python", "rust", "golang",
             "webdev", "selfhosted", "homelab", "opensource", "foss", "android",
             "apple", "hardware", "nix", "haskell", "javascript", "cpp"):
        return "tech"
    if c in ("science", "physics", "biology", "chemistry", "astronomy", "space",
             "climate", "environment"):
        return "science"
    if c in ("worldnews", "news", "politics", "usanews", "europe", "unitedkingdom"):
        return "world"
    if c in ("business", "economics", "finance", "stocks", "cryptocurrency"):
        return "business"
    if c in ("cybersecurity", "privacy", "netsec", "infosec"):
        return "security"
    if c in ("books", "movies", "music", "gaming", "games", "art", "television",
             "anime", "comics"):
        return "culture"
    return "tech"  # Lemmy skews tech
