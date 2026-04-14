"""Podcast configuration loader for Clawler."""
import logging
from pathlib import Path
from typing import List, Optional

import yaml

from clawler.models import PodcastFeed

logger = logging.getLogger(__name__)

# Default podcast feeds file location
DEFAULT_FEEDS_PATH = Path(__file__).parent / "podcast_feeds.yaml"


def load_podcast_feeds(path: Optional[str] = None) -> List[PodcastFeed]:
    """Load podcast feed configuration from YAML file.

    Args:
        path: Path to YAML config file. If None, uses built-in defaults.

    Returns:
        List of PodcastFeed objects.
    """
    config_path = Path(path) if path else DEFAULT_FEEDS_PATH

    if not config_path.exists():
        logger.warning(f"Podcast config not found at {config_path}")
        return []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading podcast config: {e}")
        return []

    if not data or "podcasts" not in data:
        return []

    feeds: List[PodcastFeed] = []
    for item in data["podcasts"]:
        try:
            feed = PodcastFeed(
                name=item.get("name", ""),
                category=item.get("category", "podcast"),
                quality_weight=float(item.get("quality_weight", 0.7)),
                enabled=item.get("enabled", True),
                spotify_id=item.get("spotify_id", ""),
                apple_id=item.get("apple_id", ""),
                youtube_channel_id=item.get("youtube_channel_id", ""),
                youtube_playlist_id=item.get("youtube_playlist_id", ""),
                rss_url=item.get("rss_url", ""),
                website_url=item.get("website_url", ""),
            )
            if feed.name:
                feeds.append(feed)
        except Exception as e:
            logger.warning(f"Error parsing podcast feed entry: {e}")

    logger.info(f"Loaded {len(feeds)} podcast feeds from {config_path}")
    return feeds


def get_feeds_by_platform(
    feeds: List[PodcastFeed],
    platform: str
) -> List[PodcastFeed]:
    """Filter feeds that have a specific platform configured.

    Args:
        feeds: List of PodcastFeed objects.
        platform: One of 'spotify', 'apple', 'youtube', 'rss'.

    Returns:
        Filtered list of feeds.
    """
    platform = platform.lower()
    result = []

    for feed in feeds:
        if not feed.enabled:
            continue
        if platform == "spotify" and feed.has_spotify:
            result.append(feed)
        elif platform == "apple" and feed.has_apple:
            result.append(feed)
        elif platform == "youtube" and feed.has_youtube:
            result.append(feed)
        elif platform == "rss" and feed.has_rss:
            result.append(feed)

    return result


def get_all_enabled_feeds(feeds: List[PodcastFeed]) -> List[PodcastFeed]:
    """Get all enabled podcast feeds."""
    return [f for f in feeds if f.enabled]
