"""Base class for podcast sources."""
from abc import abstractmethod
from typing import List, Optional
import logging
import re

from clawler.models import Article, Episode, PodcastFeed
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)


def parse_duration(duration_str: str) -> int:
    """Parse various duration formats to seconds.

    Supports:
    - HH:MM:SS or H:MM:SS
    - MM:SS or M:SS
    - ISO 8601 duration (PT1H30M45S)
    - "1 hour 30 minutes" style
    """
    if not duration_str:
        return 0

    duration_str = duration_str.strip()

    # Try HH:MM:SS or MM:SS format
    parts = duration_str.split(":")
    if len(parts) == 3:
        try:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        except ValueError:
            pass
    elif len(parts) == 2:
        try:
            m, s = map(int, parts)
            return m * 60 + s
        except ValueError:
            pass

    # Try ISO 8601 duration (PT1H30M45S)
    iso_match = re.match(
        r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$",
        duration_str,
        re.IGNORECASE
    )
    if iso_match:
        hours = int(iso_match.group(1) or 0)
        minutes = int(iso_match.group(2) or 0)
        seconds = int(iso_match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    # Try human-readable format
    total = 0
    hour_match = re.search(r"(\d+)\s*(?:hour|hr|h)", duration_str, re.IGNORECASE)
    min_match = re.search(r"(\d+)\s*(?:minute|min|m)", duration_str, re.IGNORECASE)
    sec_match = re.search(r"(\d+)\s*(?:second|sec|s)", duration_str, re.IGNORECASE)

    if hour_match:
        total += int(hour_match.group(1)) * 3600
    if min_match:
        total += int(min_match.group(1)) * 60
    if sec_match:
        total += int(sec_match.group(1))

    if total > 0:
        return total

    # Try plain seconds
    try:
        return int(float(duration_str))
    except ValueError:
        return 0


class PodcastBaseSource(BaseSource):
    """Abstract base class for podcast sources."""

    name: str = "podcast_base"
    platform: str = "unknown"  # spotify, apple, youtube, rss

    def __init__(
        self,
        feeds: Optional[List[PodcastFeed]] = None,
        limit_per_podcast: int = 10,
        min_duration_seconds: int = 0,
        max_duration_seconds: int = 0,
        category_filter: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.feeds = feeds or []
        self.limit_per_podcast = limit_per_podcast
        self.min_duration = min_duration_seconds
        self.max_duration = max_duration_seconds
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None

    @abstractmethod
    def crawl_episodes(self) -> List[Episode]:
        """Crawl podcast feeds and return episodes. Subclasses implement this."""
        ...

    def crawl(self) -> List[Article]:
        """Crawl podcast feeds and return articles (engine-compatible).

        This wraps crawl_episodes() and converts Episodes to Articles,
        preserving audio_url and other metadata in tags.
        """
        episodes = self.crawl_episodes()
        return [ep.to_article() for ep in episodes]

    def _filter_episode(self, episode: Episode) -> bool:
        """Check if episode passes configured filters."""
        # Duration filter (skip if duration is unknown/0 - we can't filter what we don't know)
        if self.min_duration > 0 and episode.duration_seconds > 0 and episode.duration_seconds < self.min_duration:
            return False
        if self.max_duration > 0 and episode.duration_seconds > 0 and episode.duration_seconds > self.max_duration:
            return False

        # Category filter
        if self.category_filter and episode.category.lower() not in self.category_filter:
            return False

        return True

    def _apply_filters(self, episodes: List[Episode]) -> List[Episode]:
        """Apply configured filters to episode list."""
        return [ep for ep in episodes if self._filter_episode(ep)]
