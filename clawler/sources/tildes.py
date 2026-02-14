"""Tildes source — scrapes tildes.net topic listings (no API key needed)."""
import logging
import re
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

TILDES_URL = "https://tildes.net/"
TILDES_GROUP_URL = "https://tildes.net/~{group}"


class TildesSource(BaseSource):
    """Fetch top topics from tildes.net via HTML scraping."""

    name = "tildes"

    def __init__(self, limit: int = 25):
        self.limit = limit

    def crawl(self) -> List[Article]:
        try:
            html = self.fetch_url(TILDES_URL)
            if not html:
                return []
        except Exception as e:
            logger.warning(f"[Tildes] Failed to fetch: {e}")
            return []

        return self._parse_topics(html)

    def _parse_topics(self, html: str) -> List[Article]:
        """Parse topic listings from Tildes HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        articles: List[Article] = []

        topics = soup.select("article.topic")
        for topic in topics[: self.limit]:
            try:
                # Title and URL
                title_el = topic.select_one("h1.topic-title a") or topic.select_one(".topic-title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                url = title_el.get("href", "")

                # External link or self-post
                link_el = topic.select_one("a.topic-info-source")
                if link_el and link_el.get("href", "").startswith("http"):
                    url = link_el["href"]
                elif url and not url.startswith("http"):
                    url = f"https://tildes.net{url}"

                if not title or not url:
                    continue

                # Discussion URL (always on Tildes)
                topic_link = topic.select_one("h1.topic-title a") or topic.select_one(".topic-title a")
                discussion_url = ""
                if topic_link:
                    href = topic_link.get("href", "")
                    if href.startswith("/"):
                        discussion_url = f"https://tildes.net{href}"
                    elif href.startswith("http"):
                        # For link topics, find the comment link
                        comment_link = topic.select_one("a.topic-info-comments")
                        if comment_link:
                            chref = comment_link.get("href", "")
                            discussion_url = f"https://tildes.net{chref}" if chref.startswith("/") else chref

                # Vote count
                votes = 0
                vote_el = topic.select_one(".topic-voting-votes")
                if vote_el:
                    try:
                        votes = int(vote_el.get_text(strip=True))
                    except (ValueError, TypeError):
                        pass

                # Comment count
                comments = 0
                comment_el = topic.select_one("a.topic-info-comments") or topic.select_one(".topic-info-comments")
                if comment_el:
                    text = comment_el.get_text(strip=True)
                    m = re.search(r"(\d+)", text)
                    if m:
                        comments = int(m.group(1))

                # Group/category
                group = ""
                group_el = topic.select_one("a.topic-group") or topic.select_one(".topic-group")
                if group_el:
                    group = group_el.get_text(strip=True).lstrip("~")

                # Timestamp
                ts = None
                time_el = topic.select_one("time")
                if time_el and time_el.get("datetime"):
                    try:
                        ts = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, AttributeError):
                        pass

                # Tags
                tags = []
                for tag_el in topic.select(".topic-tags a, .label-topic-tag"):
                    tag_text = tag_el.get_text(strip=True)
                    if tag_text:
                        tags.append(f"tildes:{tag_text}")

                category = _map_category(group)

                summary_parts = [f"Votes: {votes}"]
                summary_parts.append(f"Comments: {comments}")
                if group:
                    summary_parts.append(f"Group: ~{group}")
                if discussion_url:
                    summary_parts.append(f"Discussion: {discussion_url}")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Tildes (~{group})" if group else "Tildes",
                        summary=" | ".join(summary_parts),
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        discussion_url=discussion_url,
                    )
                )
            except Exception as e:
                logger.debug(f"[Tildes] Skipping topic: {e}")
                continue

        logger.info(f"[Tildes] Fetched {len(articles)} topics")
        return articles


def _map_category(group: str) -> str:
    """Map Tildes groups to Clawler categories."""
    g = group.lower()
    if g in ("comp", "comp.ai", "comp.programming", "comp.hardware", "comp.os", "comp.os.linux"):
        return "tech"
    if g in ("science", "science.physics", "science.biology", "science.climate"):
        return "science"
    if g in ("news", "news.politics", "news.international"):
        return "world"
    if g in ("finance", "misc.jobs"):
        return "business"
    if g in ("security", "privacy"):
        return "security"
    if g in ("arts", "music", "books", "tv", "movies", "games"):
        return "culture"
    return "tech"  # Default for Tildes (tech-leaning community)
