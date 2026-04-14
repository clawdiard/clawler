"""Apple Podcasts source — fetches episodes via iTunes API and RSS feeds."""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import feedparser

from clawler.models import Episode, PodcastFeed
from clawler.sources.podcasts.base import PodcastBaseSource, parse_duration

logger = logging.getLogger(__name__)

# iTunes lookup API
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"


class ApplePodcastsSource(PodcastBaseSource):
    """Fetch podcast episodes from Apple Podcasts via RSS feeds.

    Apple Podcasts exposes RSS feeds for all podcasts. We use the iTunes API
    to look up the feed URL from a podcast ID, then parse the RSS feed.
    """

    name = "apple_podcasts"
    platform = "apple"
    timeout = 20

    def __init__(
        self,
        podcast_ids: Optional[Dict[str, str]] = None,
        feeds: Optional[List[PodcastFeed]] = None,
        limit_per_podcast: int = 10,
        **kwargs
    ):
        super().__init__(feeds=feeds, limit_per_podcast=limit_per_podcast, **kwargs)
        # podcast_ids: {podcast_name: itunes_id}
        self.podcast_ids = podcast_ids or {}

        # Build podcast_ids from feeds if not provided directly
        if not self.podcast_ids and self.feeds:
            for feed in self.feeds:
                if feed.has_apple and feed.enabled:
                    self.podcast_ids[feed.name] = feed.apple_id

    def crawl_episodes(self) -> List[Episode]:
        """Crawl Apple Podcasts and return episodes."""
        all_episodes: List[Episode] = []
        seen_urls: set = set()

        for podcast_name, itunes_id in self.podcast_ids.items():
            try:
                episodes = self._fetch_podcast(podcast_name, itunes_id)
                for ep in episodes:
                    if ep.url not in seen_urls:
                        seen_urls.add(ep.url)
                        all_episodes.append(ep)
            except Exception as e:
                logger.warning(f"[ApplePodcasts] Error fetching {podcast_name}: {e}")

        # Apply filters
        all_episodes = self._apply_filters(all_episodes)

        logger.info(f"[ApplePodcasts] Fetched {len(all_episodes)} episodes from {len(self.podcast_ids)} podcasts")
        return all_episodes

    def _fetch_podcast(self, podcast_name: str, itunes_id: str) -> List[Episode]:
        """Fetch episodes for a single podcast."""
        # First, look up the podcast to get the RSS feed URL
        feed_url = self._get_feed_url(itunes_id)
        if not feed_url:
            logger.debug(f"[ApplePodcasts] No feed URL found for {podcast_name} ({itunes_id})")
            return []

        return self._parse_feed(feed_url, podcast_name, itunes_id)

    def _get_feed_url(self, itunes_id: str) -> Optional[str]:
        """Look up RSS feed URL from iTunes ID."""
        url = f"{ITUNES_LOOKUP_URL}?id={itunes_id}&entity=podcast"
        data = self.fetch_json(url)

        if not data or data.get("resultCount", 0) == 0:
            return None

        results = data.get("results", [])
        if not results:
            return None

        return results[0].get("feedUrl")

    def _parse_feed(self, feed_url: str, podcast_name: str, itunes_id: str) -> List[Episode]:
        """Parse RSS feed and extract episodes."""
        xml_text = self.fetch_url(feed_url)
        if not xml_text:
            return []

        feed = feedparser.parse(xml_text)
        episodes: List[Episode] = []

        # Get podcast-level metadata
        host = ""
        if hasattr(feed.feed, "author"):
            host = feed.feed.author
        elif hasattr(feed.feed, "itunes_author"):
            host = feed.feed.itunes_author

        # Use configured category from feeds, fallback to detection
        category = self._get_feed_category(podcast_name) or self._detect_category(feed)

        for entry in feed.entries[:self.limit_per_podcast]:
            try:
                episode = self._parse_entry(entry, podcast_name, itunes_id, host, category)
                if episode:
                    episodes.append(episode)
            except Exception as e:
                logger.debug(f"[ApplePodcasts] Error parsing entry in {podcast_name}: {e}")

        return episodes

    def _parse_entry(
        self,
        entry: Any,
        podcast_name: str,
        itunes_id: str,
        host: str,
        category: str
    ) -> Optional[Episode]:
        """Parse a single feed entry into an Episode."""
        title = getattr(entry, "title", "")
        if not title:
            return None

        # Episode URL (prefer link, fallback to enclosure URL)
        url = getattr(entry, "link", "")

        # Audio URL from enclosure
        audio_url = ""
        enclosures = getattr(entry, "enclosures", [])
        for enc in enclosures:
            enc_type = enc.get("type", "")
            if "audio" in enc_type or enc_type == "":
                audio_url = enc.get("href", enc.get("url", ""))
                break

        if not url:
            url = audio_url or f"https://podcasts.apple.com/podcast/id{itunes_id}"

        # Summary/description
        summary = ""
        if hasattr(entry, "summary"):
            summary = self._clean_html(entry.summary)[:500]
        elif hasattr(entry, "description"):
            summary = self._clean_html(entry.description)[:500]
        elif hasattr(entry, "itunes_summary"):
            summary = entry.itunes_summary[:500]

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

        # Guests (try to extract from title or summary)
        guests = self._extract_guests(title, summary)

        # Tags
        tags = ["apple-podcasts", f"itunes:{itunes_id}"]
        if hasattr(entry, "tags"):
            for tag in entry.tags[:5]:
                term = tag.get("term", "")
                if term:
                    tags.append(term.lower())

        # Quality score based on feed metadata
        quality = self._get_quality_score(podcast_name)

        return Episode(
            title=title,
            url=url,
            podcast_name=podcast_name,
            source_platform="apple",
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

    def _detect_category(self, feed: Any) -> str:
        """Detect category from feed metadata."""
        # Check iTunes category
        if hasattr(feed.feed, "itunes_category"):
            cat = feed.feed.itunes_category
            if isinstance(cat, dict):
                cat = cat.get("text", "")
            cat_lower = str(cat).lower()

            if any(k in cat_lower for k in ["health", "fitness", "medicine", "nutrition"]):
                return "health"
            if any(k in cat_lower for k in ["science", "natural"]):
                return "science"
            if any(k in cat_lower for k in ["sport", "recreation"]):
                return "sports"
            if any(k in cat_lower for k in ["business", "career"]):
                return "business"
            if any(k in cat_lower for k in ["tech", "computer"]):
                return "tech"
            if any(k in cat_lower for k in ["comedy", "entertainment"]):
                return "entertainment"

        return "podcast"

    def _extract_guests(self, title: str, summary: str) -> List[str]:
        """Try to extract guest names from title or summary."""
        guests = []

        # Common patterns: "with John Smith", "featuring Jane Doe", "ft. Bob"
        patterns = [
            r"(?:with|featuring|ft\.?|guest:?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:joins|discusses|talks)",
        ]

        text = f"{title} {summary}"
        for pattern in patterns:
            matches = re.findall(pattern, text)
            guests.extend(matches[:3])

        return list(set(guests))[:5]

    def _get_quality_score(self, podcast_name: str) -> float:
        """Get quality score for a podcast."""
        # Check if we have a feed config with quality weight
        for feed in self.feeds:
            if feed.name == podcast_name:
                return feed.quality_weight

        # Default quality for Apple Podcasts
        return 0.70

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
        # Simple HTML tag removal
        clean = re.sub(r"<[^>]+>", " ", text)
        # Normalize whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
