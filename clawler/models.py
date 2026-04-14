"""Data models for Clawler."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs, urlencode
import hashlib

# Query parameters known to be tracking/analytics noise (case-insensitive prefix match)
_TRACKING_PREFIXES = (
    "utm_", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
    "oly_enc_id", "oly_anon_id", "_openstat", "vero_id",
    "wickedid", "yclid", "pk_campaign", "pk_kwd", "pk_source",
    "pk_medium", "pk_content", "ref", "referrer", "source",
    "campaign", "icid", "ncid",
)


def _normalize_url(url: str) -> str:
    """Normalize a URL for dedup: strip www., trailing slash, fragment, and tracking query params."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path.rstrip("/") or "/"
        # Strip tracking query params, keep meaningful ones
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=False)
            clean = {
                k: v for k, v in params.items()
                if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
            }
            if clean:
                query = urlencode(clean, doseq=True)
                return f"{parsed.scheme}://{host}{path}?{query}"
        return f"{parsed.scheme}://{host}{path}"
    except Exception:
        return url


@dataclass
class Article:
    title: str
    url: str
    source: str
    summary: str = ""
    timestamp: Optional[datetime] = None
    category: str = "general"
    relevance: Optional[float] = None
    quality_score: float = 0.5
    source_count: int = 1  # how many sources covered this story (set during dedup)
    tags: List[str] = field(default_factory=list)  # optional tags/labels (e.g. from HN, Reddit)
    author: str = ""  # article author (when available from source)
    discussion_url: str = ""  # URL to discussion thread (HN, Lobsters, Reddit, etc.)

    @property
    def dedup_key(self) -> str:
        """Generate a deduplication key from normalized title + URL."""
        normalized = self.title.lower().strip()
        norm_url = _normalize_url(self.url)
        return hashlib.md5(f"{normalized}|{norm_url}".encode()).hexdigest()

    @property
    def title_fingerprint(self) -> str:
        """Fuzzy fingerprint based on title words for cross-source dedup.
        Returns empty string if insufficient significant words (avoids false matches)."""
        words = sorted(set(w.lower() for w in self.title.split() if len(w) > 3))
        if len(words) < 2:
            return ""  # Not enough signal for fingerprint dedup
        return hashlib.md5(" ".join(words).encode()).hexdigest()


@dataclass
class Episode:
    """Podcast episode model for discovery and ingestion."""
    title: str
    url: str                                    # Episode page URL
    podcast_name: str                           # Parent podcast name
    source_platform: str                        # spotify, apple, youtube, rss
    audio_url: str = ""                         # Direct audio/video file URL
    summary: str = ""                           # Episode description from feed
    timestamp: Optional[datetime] = None        # Publication date
    duration_seconds: int = 0                   # Episode duration
    category: str = "podcast"
    quality_score: float = 0.5
    relevance: Optional[float] = None
    source_count: int = 1  # For dedup compatibility with Article
    tags: List[str] = field(default_factory=list)
    host: str = ""                              # Podcast host name
    guests: List[str] = field(default_factory=list)
    episode_number: Optional[int] = None
    season_number: Optional[int] = None

    # Ingest-mode fields (populated after transcription/summarization)
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    key_topics: List[str] = field(default_factory=list)
    chapters: List[Dict[str, Any]] = field(default_factory=list)  # [{time_seconds, title}]

    @property
    def source(self) -> str:
        """Compatibility with Article interface."""
        return f"Podcast ({self.podcast_name})"

    @property
    def duration_formatted(self) -> str:
        """Human-readable duration string."""
        if self.duration_seconds <= 0:
            return ""
        hours, remainder = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @property
    def dedup_key(self) -> str:
        """Generate a deduplication key from normalized title + podcast name."""
        normalized = self.title.lower().strip()
        podcast = self.podcast_name.lower().strip()
        return hashlib.md5(f"{podcast}|{normalized}".encode()).hexdigest()

    @property
    def title_fingerprint(self) -> str:
        """Fuzzy fingerprint for cross-platform dedup of same episode."""
        words = sorted(set(w.lower() for w in self.title.split() if len(w) > 3))
        if len(words) < 2:
            return ""
        return hashlib.md5(" ".join(words).encode()).hexdigest()

    def to_article(self) -> Article:
        """Convert Episode to Article for unified output formatting."""
        duration_tag = f"duration:{self.duration_formatted}" if self.duration_formatted else ""
        tags = ["podcast", f"platform:{self.source_platform}"] + self.tags
        if duration_tag:
            tags.append(duration_tag)
        # Preserve audio_url in tags for ingest mode
        if self.audio_url:
            tags.append(f"audio_url:{self.audio_url}")

        summary_parts = []
        if self.duration_formatted:
            summary_parts.append(f"⏱️ {self.duration_formatted}")
        if self.host:
            summary_parts.append(f"Host: {self.host}")
        if self.guests:
            summary_parts.append(f"Guests: {', '.join(self.guests[:3])}")
        if self.summary:
            summary_parts.append(self.summary)

        return Article(
            title=self.title,
            url=self.url,
            source=self.source,
            summary=" | ".join(summary_parts) if summary_parts else self.summary,
            timestamp=self.timestamp,
            category=self.category,
            relevance=self.relevance,
            quality_score=self.quality_score,
            tags=tags,
            author=self.host,
        )


@dataclass
class PodcastFeed:
    """Configuration for a podcast feed source."""
    name: str
    category: str = "health"
    quality_weight: float = 0.7
    enabled: bool = True

    # Platform-specific identifiers (use whichever are available)
    spotify_id: str = ""                # Spotify show ID
    apple_id: str = ""                  # Apple Podcasts / iTunes ID
    youtube_channel_id: str = ""        # YouTube channel ID
    youtube_playlist_id: str = ""       # YouTube playlist ID
    rss_url: str = ""                   # Direct RSS feed URL
    website_url: str = ""               # Podcast website

    @property
    def has_spotify(self) -> bool:
        return bool(self.spotify_id)

    @property
    def has_apple(self) -> bool:
        return bool(self.apple_id)

    @property
    def has_youtube(self) -> bool:
        return bool(self.youtube_channel_id or self.youtube_playlist_id)

    @property
    def has_rss(self) -> bool:
        return bool(self.rss_url)
