"""Spotify Podcasts source — fetches episodes via Spotify Web API."""
import base64
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from clawler.models import Episode, PodcastFeed
from clawler.sources.podcasts.base import PodcastBaseSource

logger = logging.getLogger(__name__)

# Spotify API endpoints
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


class SpotifyPodcastSource(PodcastBaseSource):
    """Fetch podcast episodes from Spotify via Web API.

    Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.
    Uses Client Credentials flow (no user auth needed for public podcast data).
    """

    name = "spotify_podcasts"
    platform = "spotify"
    timeout = 20

    def __init__(
        self,
        show_ids: Optional[Dict[str, str]] = None,
        feeds: Optional[List[PodcastFeed]] = None,
        limit_per_podcast: int = 10,
        market: str = "US",
        **kwargs
    ):
        super().__init__(feeds=feeds, limit_per_podcast=limit_per_podcast, **kwargs)
        # show_ids: {podcast_name: spotify_show_id}
        self.show_ids = show_ids or {}
        self.market = market

        # Build show_ids from feeds if not provided directly
        if not self.show_ids and self.feeds:
            for feed in self.feeds:
                if feed.has_spotify and feed.enabled:
                    self.show_ids[feed.name] = feed.spotify_id

        # Auth credentials
        self._client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
        self._client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        self._access_token: Optional[str] = None

    def _authenticate(self) -> bool:
        """Get access token using Client Credentials flow."""
        if not self._client_id or not self._client_secret:
            logger.warning("[Spotify] No SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET found")
            return False

        # Base64 encode credentials
        credentials = f"{self._client_id}:{self._client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        # Request token
        import requests
        try:
            resp = requests.post(
                SPOTIFY_AUTH_URL,
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data.get("access_token")
            return bool(self._access_token)
        except Exception as e:
            logger.warning(f"[Spotify] Auth failed: {e}")
            return False

    def _api_get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated GET request to Spotify API."""
        if not self._access_token:
            if not self._authenticate():
                return None

        url = f"{SPOTIFY_API_BASE}{endpoint}"
        import requests
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[Spotify] API request failed: {e}")
            return None

    def crawl_episodes(self) -> List[Episode]:
        """Crawl Spotify podcasts and return episodes."""
        if not self.show_ids:
            logger.info("[Spotify] No podcast IDs configured")
            return []

        if not self._client_id or not self._client_secret:
            logger.warning(
                "[Spotify] Skipping — set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
                "env vars to enable Spotify podcast source"
            )
            return []

        all_episodes: List[Episode] = []
        seen_urls: set = set()

        for podcast_name, show_id in self.show_ids.items():
            try:
                episodes = self._fetch_show_episodes(podcast_name, show_id)
                for ep in episodes:
                    if ep.url not in seen_urls:
                        seen_urls.add(ep.url)
                        all_episodes.append(ep)
            except Exception as e:
                logger.warning(f"[Spotify] Error fetching {podcast_name}: {e}")

        # Apply filters
        all_episodes = self._apply_filters(all_episodes)

        logger.info(f"[Spotify] Fetched {len(all_episodes)} episodes from {len(self.show_ids)} podcasts")
        return all_episodes

    def _fetch_show_episodes(self, podcast_name: str, show_id: str) -> List[Episode]:
        """Fetch episodes for a single show."""
        # Get show details first
        show_data = self._api_get(f"/shows/{show_id}", {"market": self.market})
        if not show_data:
            return []

        # Extract show metadata
        host = show_data.get("publisher", "")
        category = self._detect_category(show_data)

        # Get episodes
        episodes_data = self._api_get(
            f"/shows/{show_id}/episodes",
            {
                "market": self.market,
                "limit": min(self.limit_per_podcast, 50),  # Spotify max is 50
            }
        )

        if not episodes_data:
            return []

        episodes: List[Episode] = []
        for item in episodes_data.get("items", []):
            try:
                episode = self._parse_episode(item, podcast_name, show_id, host, category)
                if episode:
                    episodes.append(episode)
            except Exception as e:
                logger.debug(f"[Spotify] Error parsing episode in {podcast_name}: {e}")

        return episodes

    def _parse_episode(
        self,
        item: Dict[str, Any],
        podcast_name: str,
        show_id: str,
        host: str,
        category: str
    ) -> Optional[Episode]:
        """Parse Spotify episode data into Episode model."""
        title = item.get("name", "")
        if not title:
            return None

        # URLs
        url = item.get("external_urls", {}).get("spotify", "")
        if not url:
            url = f"https://open.spotify.com/episode/{item.get('id', '')}"

        # Audio URL (Spotify doesn't provide direct audio URLs via API)
        audio_url = item.get("audio_preview_url", "")

        # Summary
        summary = item.get("description", "")[:500]
        if not summary:
            summary = item.get("html_description", "")[:500]

        # Timestamp
        timestamp = None
        release_date = item.get("release_date")
        if release_date:
            try:
                # Handle different precision levels
                if len(release_date) == 10:  # YYYY-MM-DD
                    timestamp = datetime.strptime(release_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                elif len(release_date) == 7:  # YYYY-MM
                    timestamp = datetime.strptime(release_date, "%Y-%m").replace(tzinfo=timezone.utc)
                elif len(release_date) == 4:  # YYYY
                    timestamp = datetime.strptime(release_date, "%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # Duration (Spotify provides in milliseconds)
        duration_ms = item.get("duration_ms", 0)
        duration_seconds = duration_ms // 1000 if duration_ms else 0

        # Tags
        tags = ["spotify", f"spotify:show:{show_id}", f"spotify:episode:{item.get('id', '')}"]
        if item.get("explicit"):
            tags.append("explicit")

        # Quality score
        quality = self._get_quality_score(podcast_name)

        return Episode(
            title=title,
            url=url,
            podcast_name=podcast_name,
            source_platform="spotify",
            audio_url=audio_url,
            summary=summary,
            timestamp=timestamp,
            duration_seconds=duration_seconds,
            category=category,
            quality_score=quality,
            tags=tags,
            host=host,
        )

    def _detect_category(self, show_data: Dict[str, Any]) -> str:
        """Detect category from show metadata."""
        # Check explicit categories
        categories = show_data.get("genres", [])
        for cat in categories:
            cat_lower = cat.lower()
            if any(k in cat_lower for k in ["health", "fitness", "medicine", "nutrition", "wellness"]):
                return "health"
            if any(k in cat_lower for k in ["science", "nature"]):
                return "science"
            if any(k in cat_lower for k in ["sport"]):
                return "sports"
            if any(k in cat_lower for k in ["business", "career", "entrepreneur"]):
                return "business"
            if any(k in cat_lower for k in ["tech", "computer"]):
                return "tech"
            if any(k in cat_lower for k in ["comedy", "entertainment"]):
                return "entertainment"

        # Check description for keywords
        description = show_data.get("description", "").lower()
        if any(k in description for k in ["health", "fitness", "nutrition", "wellness", "longevity"]):
            return "health"
        if any(k in description for k in ["science", "research"]):
            return "science"

        return "podcast"

    def _get_quality_score(self, podcast_name: str) -> float:
        """Get quality score for a podcast."""
        for feed in self.feeds:
            if feed.name == podcast_name:
                return feed.quality_weight
        return 0.70
