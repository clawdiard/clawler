"""Generic Podcast RSS source — fetches episodes from any podcast RSS feed."""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import feedparser

from clawler.models import Episode, PodcastFeed
from clawler.sources.podcasts.base import PodcastBaseSource, parse_duration

logger = logging.getLogger(__name__)


class PodcastRSSSource(PodcastBaseSource):
    """Fetch podcast episodes from generic RSS/Atom feeds.

    Works with any standard podcast RSS feed (most podcasts publish RSS).
    """

    name = "podcast_rss"
    platform = "rss"
    timeout = 20

    def __init__(
        self,
        feed_urls: Optional[Dict[str, str]] = None,
        feeds: Optional[List[PodcastFeed]] = None,
        limit_per_podcast: int = 10,
        **kwargs
    ):
        super().__init__(feeds=feeds, limit_per_podcast=limit_per_podcast, **kwargs)
        # feed_urls: {podcast_name: rss_url}
        self.feed_urls = feed_urls or {}

        # Build from feeds config if not provided directly
        if not self.feed_urls and self.feeds:
            for feed in self.feeds:
                if feed.has_rss and feed.enabled:
                    self.feed_urls[feed.name] = feed.rss_url

    def crawl_episodes(self) -> List[Episode]:
        """Crawl RSS feeds and return episodes."""
        all_episodes: List[Episode] = []
        seen_urls: set = set()

        for podcast_name, feed_url in self.feed_urls.items():
            try:
                episodes = self._fetch_feed(podcast_name, feed_url)
                for ep in episodes:
                    if ep.url not in seen_urls:
                        seen_urls.add(ep.url)
                        all_episodes.append(ep)
            except Exception as e:
                logger.warning(f"[PodcastRSS] Error fetching {podcast_name}: {e}")

        # Apply filters
        all_episodes = self._apply_filters(all_episodes)

        logger.info(f"[PodcastRSS] Fetched {len(all_episodes)} episodes from {len(self.feed_urls)} feeds")
        return all_episodes

    def _fetch_feed(self, podcast_name: str, feed_url: str) -> List[Episode]:
        """Fetch and parse a single RSS feed."""
        xml_text = self.fetch_url(feed_url)
        if not xml_text:
            return []

        feed = feedparser.parse(xml_text)
        episodes: List[Episode] = []

        # Extract podcast-level metadata
        host = self._get_host(feed)
        # Use configured category from feeds, fallback to detection
        category = self._get_feed_category(podcast_name) or self._detect_category(feed, podcast_name)
        podcast_image = self._get_image(feed)

        for entry in feed.entries[:self.limit_per_podcast]:
            try:
                episode = self._parse_entry(entry, podcast_name, feed_url, host, category)
                if episode:
                    episodes.append(episode)
            except Exception as e:
                logger.debug(f"[PodcastRSS] Error parsing entry in {podcast_name}: {e}")

        return episodes

    def _parse_entry(
        self,
        entry: Any,
        podcast_name: str,
        feed_url: str,
        host: str,
        category: str
    ) -> Optional[Episode]:
        """Parse a feed entry into an Episode."""
        title = getattr(entry, "title", "")
        if not title:
            return None

        # Episode URL
        url = getattr(entry, "link", "")

        # Audio URL from enclosure
        audio_url = ""
        enclosures = getattr(entry, "enclosures", [])
        for enc in enclosures:
            enc_type = enc.get("type", "")
            if "audio" in enc_type or enc_type == "":
                audio_url = enc.get("href", enc.get("url", ""))
                break

        # Fallback: check for media:content
        if not audio_url:
            media_content = getattr(entry, "media_content", [])
            for mc in media_content:
                if "audio" in mc.get("type", ""):
                    audio_url = mc.get("url", "")
                    break

        if not url:
            url = audio_url

        if not url:
            return None

        # Summary
        summary = ""
        for attr in ["summary", "description", "content", "itunes_summary"]:
            val = getattr(entry, attr, None)
            if val:
                if isinstance(val, list) and val:
                    val = val[0].get("value", "") if isinstance(val[0], dict) else str(val[0])
                summary = self._clean_html(str(val))[:500]
                break

        # Timestamp
        timestamp = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                timestamp = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        # Duration
        duration_seconds = 0
        if hasattr(entry, "itunes_duration"):
            duration_seconds = parse_duration(entry.itunes_duration)
        elif hasattr(entry, "duration"):
            duration_seconds = parse_duration(str(entry.duration))

        # Episode/season numbers
        episode_number = None
        season_number = None
        if hasattr(entry, "itunes_episode"):
            try:
                episode_number = int(entry.itunes_episode)
            except (ValueError, TypeError):
                pass
        if hasattr(entry, "itunes_season"):
            try:
                season_number = int(entry.itunes_season)
            except (ValueError, TypeError):
                pass

        # Episode-specific author (guest?)
        episode_author = ""
        if hasattr(entry, "author"):
            episode_author = entry.author
        elif hasattr(entry, "itunes_author"):
            episode_author = entry.itunes_author

        # Try to extract guests
        guests = self._extract_guests(title, summary, episode_author)

        # Tags from entry
        tags = ["podcast-rss"]
        if hasattr(entry, "tags"):
            for tag in entry.tags[:5]:
                term = tag.get("term", "")
                if term:
                    tags.append(term.lower().replace(" ", "-"))

        # Quality score
        quality = self._get_quality_score(podcast_name)

        return Episode(
            title=title,
            url=url,
            podcast_name=podcast_name,
            source_platform="rss",
            audio_url=audio_url,
            summary=summary,
            timestamp=timestamp,
            duration_seconds=duration_seconds,
            category=category,
            quality_score=quality,
            tags=tags,
            host=host,
            guests=guests,
            episode_number=episode_number,
            season_number=season_number,
        )

    def _get_host(self, feed: Any) -> str:
        """Extract host/author from feed metadata."""
        if hasattr(feed.feed, "author"):
            return feed.feed.author
        if hasattr(feed.feed, "itunes_author"):
            return feed.feed.itunes_author
        if hasattr(feed.feed, "managingEditor"):
            return feed.feed.managingEditor
        return ""

    def _get_image(self, feed: Any) -> str:
        """Extract podcast image URL."""
        if hasattr(feed.feed, "image"):
            img = feed.feed.image
            if hasattr(img, "href"):
                return img.href
            if hasattr(img, "url"):
                return img.url
        if hasattr(feed.feed, "itunes_image"):
            return feed.feed.itunes_image.get("href", "")
        return ""

    def _detect_category(self, feed: Any, podcast_name: str) -> str:
        """Detect category from feed metadata."""
        # Check iTunes category
        if hasattr(feed.feed, "itunes_category"):
            cat = feed.feed.itunes_category
            if isinstance(cat, dict):
                cat = cat.get("text", "")
            elif isinstance(cat, list) and cat:
                cat = cat[0].get("text", "") if isinstance(cat[0], dict) else str(cat[0])
            cat_lower = str(cat).lower()

            category_map = {
                "health": ["health", "fitness", "medicine", "nutrition", "wellness", "mental"],
                "science": ["science", "natural", "technology"],
                "sports": ["sport", "recreation", "football", "basketball"],
                "business": ["business", "career", "entrepreneur", "invest"],
                "tech": ["tech", "computer", "software"],
                "entertainment": ["comedy", "entertainment", "tv", "film"],
                "education": ["education", "learning", "courses"],
            }

            for cat_name, keywords in category_map.items():
                if any(k in cat_lower for k in keywords):
                    return cat_name

        # Check feed description
        description = getattr(feed.feed, "description", "").lower()
        title = getattr(feed.feed, "title", "").lower()
        text = f"{description} {title} {podcast_name.lower()}"

        if any(k in text for k in ["health", "fitness", "nutrition", "wellness", "longevity"]):
            return "health"
        if any(k in text for k in ["science", "research"]):
            return "science"
        if any(k in text for k in ["sport", "athletic"]):
            return "sports"
        if any(k in text for k in ["business", "entrepreneur"]):
            return "business"

        return "podcast"

    def _extract_guests(self, title: str, summary: str, episode_author: str) -> List[str]:
        """Extract guest names."""
        guests = []
        text = f"{title} {summary}"

        # If episode has different author than show, might be a guest
        if episode_author and episode_author not in title:
            guests.append(episode_author)

        patterns = [
            r"(?:with|featuring|ft\.?|guest:?|w/)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:joins|discusses|talks|interview)",
            r"(?:Dr\.?|Prof\.?|MD)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            guests.extend(matches[:3])

        return list(set(guests))[:5]

    def _get_quality_score(self, podcast_name: str) -> float:
        """Get quality score for a podcast."""
        for feed in self.feeds:
            if feed.name == podcast_name:
                return feed.quality_weight
        return 0.65

    def _get_feed_category(self, podcast_name: str) -> Optional[str]:
        """Get configured category for a podcast from feeds config."""
        for feed in self.feeds:
            if feed.name == podcast_name:
                return feed.category
        return None

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text."""
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
