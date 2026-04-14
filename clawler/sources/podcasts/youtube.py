"""YouTube Podcasts source — fetches podcast episodes from YouTube channels/playlists."""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional, Dict, Set

from clawler.models import Episode, PodcastFeed
from clawler.sources.podcasts.base import PodcastBaseSource

logger = logging.getLogger(__name__)

# YouTube RSS feed URLs
YOUTUBE_CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_PLAYLIST_FEED = "https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"

# XML namespaces
ATOM_NS = "http://www.w3.org/2005/Atom"
MEDIA_NS = "http://search.yahoo.com/mrss/"
YT_NS = "http://www.youtube.com/xml/schemas/2015"


class YouTubePodcastSource(PodcastBaseSource):
    """Fetch podcast episodes from YouTube channels and playlists.

    Focuses on long-form content (>20 minutes by default) typical of podcasts.
    Uses YouTube RSS feeds (no API key required).
    """

    name = "youtube_podcasts"
    platform = "youtube"
    timeout = 20

    # Default minimum duration for podcast content (20 minutes)
    DEFAULT_MIN_DURATION = 1200

    def __init__(
        self,
        channels: Optional[Dict[str, str]] = None,
        playlists: Optional[Dict[str, str]] = None,
        feeds: Optional[List[PodcastFeed]] = None,
        limit_per_channel: int = 10,
        min_duration_seconds: int = 0,
        exclude_shorts: bool = True,
        **kwargs
    ):
        # Set default min duration for podcasts if not specified
        if min_duration_seconds == 0:
            min_duration_seconds = self.DEFAULT_MIN_DURATION

        super().__init__(
            feeds=feeds,
            limit_per_podcast=limit_per_channel,
            min_duration_seconds=min_duration_seconds,
            **kwargs
        )

        # channels: {channel_name: channel_id}
        self.channels = channels or {}
        # playlists: {playlist_name: playlist_id}
        self.playlists = playlists or {}
        self.exclude_shorts = exclude_shorts

        # Build from feeds if not provided directly
        if not self.channels and not self.playlists and self.feeds:
            for feed in self.feeds:
                if feed.enabled:
                    if feed.youtube_channel_id:
                        self.channels[feed.name] = feed.youtube_channel_id
                    if feed.youtube_playlist_id:
                        self.playlists[feed.name] = feed.youtube_playlist_id

    def crawl_episodes(self) -> List[Episode]:
        """Crawl YouTube channels/playlists and return episodes."""
        all_episodes: List[Episode] = []
        seen_urls: Set[str] = set()

        # Crawl channels
        for channel_name, channel_id in self.channels.items():
            try:
                url = YOUTUBE_CHANNEL_FEED.format(channel_id=channel_id)
                episodes = self._fetch_feed(url, channel_name, channel_id, is_playlist=False)
                for ep in episodes:
                    if ep.url not in seen_urls:
                        seen_urls.add(ep.url)
                        all_episodes.append(ep)
            except Exception as e:
                logger.warning(f"[YouTubePodcasts] Error fetching channel {channel_name}: {e}")

        # Crawl playlists
        for playlist_name, playlist_id in self.playlists.items():
            try:
                url = YOUTUBE_PLAYLIST_FEED.format(playlist_id=playlist_id)
                episodes = self._fetch_feed(url, playlist_name, playlist_id, is_playlist=True)
                for ep in episodes:
                    if ep.url not in seen_urls:
                        seen_urls.add(ep.url)
                        all_episodes.append(ep)
            except Exception as e:
                logger.warning(f"[YouTubePodcasts] Error fetching playlist {playlist_name}: {e}")

        # Apply filters
        all_episodes = self._apply_filters(all_episodes)

        total_sources = len(self.channels) + len(self.playlists)
        logger.info(f"[YouTubePodcasts] Fetched {len(all_episodes)} episodes from {total_sources} sources")
        return all_episodes

    def _fetch_feed(
        self,
        feed_url: str,
        source_name: str,
        source_id: str,
        is_playlist: bool
    ) -> List[Episode]:
        """Fetch and parse a YouTube RSS feed."""
        xml_text = self.fetch_url(feed_url)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug(f"[YouTubePodcasts] XML parse error for {source_name}: {e}")
            return []

        ns = {"atom": ATOM_NS, "media": MEDIA_NS, "yt": YT_NS}
        entries = root.findall("atom:entry", ns)
        episodes: List[Episode] = []

        # Get channel-level author
        channel_author = ""
        author_el = root.find("atom:author/atom:name", ns)
        if author_el is not None and author_el.text:
            channel_author = author_el.text

        for entry in entries[:self.limit_per_podcast]:
            try:
                episode = self._parse_entry(
                    entry, ns, source_name, source_id, channel_author, is_playlist
                )
                if episode:
                    episodes.append(episode)
            except Exception as e:
                logger.debug(f"[YouTubePodcasts] Error parsing entry in {source_name}: {e}")

        return episodes

    def _parse_entry(
        self,
        entry: ET.Element,
        ns: Dict[str, str],
        source_name: str,
        source_id: str,
        channel_author: str,
        is_playlist: bool
    ) -> Optional[Episode]:
        """Parse a single feed entry into an Episode."""
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        published_el = entry.find("atom:published", ns)
        video_id_el = entry.find("yt:videoId", ns)
        media_group = entry.find("media:group", ns)
        author_el = entry.find("atom:author/atom:name", ns)

        title = title_el.text if title_el is not None and title_el.text else ""
        if not title:
            return None

        video_url = link_el.get("href", "") if link_el is not None else ""
        video_id = video_id_el.text if video_id_el is not None else ""

        if not video_url and video_id:
            video_url = f"https://www.youtube.com/watch?v={video_id}"

        # Skip shorts
        if self.exclude_shorts and "/shorts/" in video_url:
            return None

        # Summary from media:description
        summary = ""
        if media_group is not None:
            desc_el = media_group.find("media:description", ns)
            if desc_el is not None and desc_el.text:
                summary = desc_el.text[:500].strip()

        # Timestamp
        timestamp = None
        if published_el is not None and published_el.text:
            try:
                ts_str = published_el.text.replace("Z", "+00:00")
                timestamp = datetime.fromisoformat(ts_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                pass

        # Author/Host
        host = author_el.text if author_el is not None and author_el.text else channel_author

        # Duration (not available in RSS feed, would need API)
        # We'll set to 0 and rely on min_duration filter being disabled or video metadata
        duration_seconds = 0

        # Try to extract duration from title (some podcasts include it)
        duration_match = re.search(r"(\d+)\s*(?:hr|hour|h)\s*(?:(\d+)\s*(?:min|m))?", title, re.I)
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2) or 0)
            duration_seconds = hours * 3600 + minutes * 60
        else:
            min_match = re.search(r"(\d+)\s*(?:min|minute|m)\b", title, re.I)
            if min_match:
                duration_seconds = int(min_match.group(1)) * 60

        # Views (from media:statistics)
        views = 0
        if media_group is not None:
            stats = media_group.find("media:community/media:statistics", ns)
            if stats is not None:
                views_str = stats.get("views", "")
                if views_str:
                    try:
                        views = int(views_str)
                    except ValueError:
                        pass

        # Detect guests from title
        guests = self._extract_guests(title, summary)

        # Category detection
        category = self._detect_category(title, summary, source_name)

        # Tags
        tags = [
            "youtube",
            f"yt:channel:{source_id}" if not is_playlist else f"yt:playlist:{source_id}",
        ]
        if video_id:
            tags.append(f"yt:video:{video_id}")
        if is_playlist:
            tags.append("yt:playlist")

        # Quality score
        quality = self._get_quality_score(source_name, views)

        return Episode(
            title=title,
            url=video_url,
            podcast_name=source_name,
            source_platform="youtube",
            audio_url=video_url,  # YouTube videos are video, not audio-only
            summary=summary,
            timestamp=timestamp,
            duration_seconds=duration_seconds,
            category=category,
            quality_score=quality,
            tags=tags,
            host=host,
            guests=guests,
        )

    def _extract_guests(self, title: str, summary: str) -> List[str]:
        """Extract guest names from title or summary."""
        guests = []
        text = f"{title} {summary}"

        patterns = [
            r"(?:with|featuring|ft\.?|guest:?|w/)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:joins|discusses|talks|interview)",
            r"(?:Dr\.?|Prof\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            guests.extend(matches[:3])

        return list(set(guests))[:5]

    def _detect_category(self, title: str, summary: str, source_name: str) -> str:
        """Detect category from content."""
        text = f"{title} {summary} {source_name}".lower()

        if any(k in text for k in ["health", "fitness", "nutrition", "wellness", "longevity", "diet", "sleep", "medical"]):
            return "health"
        if any(k in text for k in ["science", "research", "study", "experiment"]):
            return "science"
        if any(k in text for k in ["sport", "nfl", "nba", "football", "basketball", "athletic"]):
            return "sports"
        if any(k in text for k in ["business", "entrepreneur", "startup", "invest"]):
            return "business"
        if any(k in text for k in ["tech", "ai", "software", "coding"]):
            return "tech"

        return "podcast"

    def _get_quality_score(self, source_name: str, views: int) -> float:
        """Calculate quality score based on source and engagement."""
        # Check feed config first
        for feed in self.feeds:
            if feed.name == source_name:
                return feed.quality_weight

        # Fallback: calculate from views
        if views > 0:
            import math
            # log10(1M) = 6 -> 0.75, log10(100k) = 5 -> 0.625
            raw = math.log10(max(views, 1)) / 8.0
            return min(max(round(raw, 2), 0.3), 0.85)

        return 0.65
