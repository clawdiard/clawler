"""YouTube RSS source — fetches latest videos from YouTube channel RSS feeds (no API key needed)."""
import logging
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional, Set
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

YOUTUBE_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_PLAYLIST_FEED_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
SHORTS_URL_PATTERN = re.compile(r"/shorts/")

# Curated list of high-quality channels across categories (no API key needed)
DEFAULT_CHANNELS = {
    # Tech / CS
    "UCsBjURrPoezykLs9EqgamOA": "Fireship",
    "UCWN3xxRkmTPmbKwht9FuE5A": "Siraj Raval",
    "UCvjgXvBlbQIFgxNjLMq5FhQ": "Tom Scott",
    "UC8butISFwT-Wl7EV0hUK0BQ": "freeCodeCamp",
    "UCXv1JCOwgl2SCbB1tgLMVXg": "Traversy Media",
    "UCVHFbqXqoYvEWM1Ddxl0QDg": "Android Developers",
    "UCnUYZLuoy1rq1aVMwx4aTzw": "Google Chrome Developers",
    # AI / ML
    "UCNJ1Ymd5yFuUPtn21xtRbbw": "AI Explained",
    "UCbfYPyITQ-7l4upoX8nvctg": "Two Minute Papers",
    "UCZHmQk67mSJgfCCTn7xBfew": "Bycloud",
    "UCWN3xxRkmTPmbKwht9FuE5A": "Siraj Raval",
    "UCr8O8l5cCX85Oem1d18EezQ": "sentdex",
    # Science
    "UC6nSFpj9HTCZ5t-N3Rm3-HA": "Vsauce",
    "UCHnyfMqiRRG1u-2MsSQLbXA": "Veritasium",
    "UCUHW94eEFW7hkUMVaZz4eDg": "minutephysics",
    "UC7_gcs09iThXybpVgjHR_7g": "PBS Space Time",
    "UCZYTClx2T1of7BRZ86-8fow": "SciShow",
    "UC9-y-6csu5WGm29I7JiwpnA": "Computerphile",
    # Business / Finance
    "UCnMn36GP_RN8OCD6mJMOxKA": "How Money Works",
    "UCV6KDgJskWaEckne5aPA0aQ": "Graham Stephan",
    "UC4xqGIZbpcedIRjA05YeBTw": "Patrick Boyle",
    "UCL_f53ZEJxp8TtlOkHwMV9Q": "Jordan Harbinger",
    # Design / Creative
    "UCKqH_9mk1waLgBiL2vT5b9g": "The Futur",
    "UCJ0-OtVpF0wOKEqT2Z1HEtA": "Elizabeth Filips",
    # News / Current Events
    "UCupvZG-5ko_eiXAupbDfxWw": "CNN",
    "UCIRYBXDze5krPDzAEOxFGVA": "Johnny Harris",
    "UCaXkIU1QidjPwiAYu6GcHjg": "TLDR News Global",
    # Gaming
    "UCNvzD7Z-g64bPXxGzaQaa4g": "Game Maker's Toolkit",
    # Skateboarding
    "UCusN3jlUbUnJGbyFwE1BfOg": "Braille Skateboarding",
    "UC9PgszLOAWhQC6orYejcJlw": "The Berrics",
}

MEDIA_NS = "http://search.yahoo.com/mrss/"
YT_NS = "http://www.youtube.com/xml/schemas/2015"

# Keyword-based category detection (checked against title, lowercased)
CATEGORY_KEYWORDS = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "gpt", "llm", "chatgpt", "openai", "transformer", "diffusion", "stable diffusion",
        "midjourney", "ai model", "language model", "generative ai", "computer vision",
        "reinforcement learning", "nlp", "natural language",
    ],
    "security": [
        "hack", "exploit", "vulnerability", "malware", "ransomware", "phishing",
        "cybersecurity", "zero-day", "data breach", "encryption", "privacy",
    ],
    "crypto": [
        "bitcoin", "ethereum", "crypto", "blockchain", "defi", "nft", "web3", "solana",
    ],
    "science": [
        "quantum", "physics", "biology", "chemistry", "astronomy", "space", "nasa",
        "telescope", "particle", "genome", "evolution", "climate", "neuroscience",
    ],
    "business": [
        "startup", "venture capital", "ipo", "acquisition", "revenue", "stock market",
        "economy", "inflation", "interest rate", "fed ", "gdp", "earnings",
    ],
    "gaming": [
        "game design", "video game", "playstation", "xbox", "nintendo", "steam",
        "esports", "speedrun", "indie game",
    ],
    "design": [
        "ui design", "ux design", "figma", "typography", "graphic design", "branding",
        "web design", "color theory",
    ],
    "health": [
        "health", "medical", "vaccine", "clinical trial", "mental health", "nutrition",
        "fitness", "exercise", "wellness",
    ],
}


def _detect_category_from_title(title: str) -> Optional[str]:
    """Detect category from video title using keyword matching."""
    title_lower = title.lower()
    scores: dict[str, int] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                scores[cat] = scores.get(cat, 0) + 1
    if not scores:
        return None
    return max(scores, key=scores.get)


def _format_views(views: int) -> str:
    """Format view count human-readably."""
    if views >= 1_000_000:
        return f"{views / 1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views / 1_000:.1f}K"
    return str(views)


def _quality_score(views: int, channel_name: str) -> float:
    """Compute quality score 0–1 based on view count (log scale)."""
    if views <= 0:
        return 0.3  # unknown views, neutral
    # log10(1000)=3 → 0.3, log10(100k)=5 → 0.5, log10(1M)=6 → 0.6, log10(10M)=7 → 0.7
    # Scale so 100 views ≈ 0.2, 1M views ≈ 0.8, 10M+ ≈ 0.95
    raw = math.log10(max(views, 1)) / 8.0  # log10(100M)=8 → 1.0
    return min(max(round(raw, 2), 0.05), 0.95)


class YouTubeSource(BaseSource):
    """Fetch latest videos from YouTube channels via RSS (no API key)."""

    name = "youtube"
    timeout = 20

    def __init__(
        self,
        channels: dict | None = None,
        playlists: dict | None = None,
        limit_per_channel: int = 5,
        limit: int | None = None,
        exclude_shorts: bool = True,
        min_views: int = 0,
        category_filter: list[str] | None = None,
    ):
        self.channels = channels or DEFAULT_CHANNELS
        self.playlists = playlists or {}
        self.limit_per_channel = limit_per_channel
        self.limit = limit
        self.exclude_shorts = exclude_shorts
        self.min_views = min_views
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        articles: List[Article] = []

        # Channels
        for channel_id, channel_name in self.channels.items():
            try:
                url = YOUTUBE_FEED_URL.format(channel_id=channel_id)
                arts = self._fetch_feed(url, channel_name)
                for a in arts:
                    if a.url not in seen_urls:
                        seen_urls.add(a.url)
                        articles.append(a)
            except Exception as e:
                logger.debug(f"[YouTube] Error fetching {channel_name}: {e}")

        # Playlists
        for playlist_id, playlist_name in self.playlists.items():
            try:
                url = YOUTUBE_PLAYLIST_FEED_URL.format(playlist_id=playlist_id)
                arts = self._fetch_feed(url, playlist_name, is_playlist=True)
                for a in arts:
                    if a.url not in seen_urls:
                        seen_urls.add(a.url)
                        articles.append(a)
            except Exception as e:
                logger.debug(f"[YouTube] Error fetching playlist {playlist_name}: {e}")

        # Apply category filter
        if self.category_filter:
            articles = [a for a in articles if a.category in self.category_filter]

        # Apply global limit
        if self.limit is not None:
            articles = articles[: self.limit]

        logger.info(f"[YouTube] Fetched {len(articles)} videos from {len(self.channels)} channels + {len(self.playlists)} playlists")
        return articles

    def _fetch_feed(self, feed_url: str, feed_name: str, is_playlist: bool = False) -> List[Article]:
        xml_text = self.fetch_url(feed_url)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug(f"[YouTube] XML parse error for {feed_name}: {e}")
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom", "media": MEDIA_NS, "yt": YT_NS}
        entries = root.findall("atom:entry", ns)
        articles: List[Article] = []

        for entry in entries[: self.limit_per_channel]:
            try:
                art = self._parse_entry(entry, ns, feed_name, is_playlist)
                if art is not None:
                    articles.append(art)
            except Exception as e:
                logger.debug(f"[YouTube] Skipping entry in {feed_name}: {e}")
                continue

        return articles

    def _parse_entry(self, entry, ns: dict, feed_name: str, is_playlist: bool) -> Optional[Article]:
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        published_el = entry.find("atom:published", ns)
        media_group = entry.find("media:group", ns)
        author_el = entry.find("atom:author/atom:name", ns)

        title = title_el.text if title_el is not None else ""
        video_url = link_el.get("href", "") if link_el is not None else ""
        if not title or not video_url:
            return None

        # Shorts filtering
        if self.exclude_shorts and SHORTS_URL_PATTERN.search(video_url):
            return None

        # Video ID extraction for shorts detection via title heuristics
        video_id_el = entry.find("yt:videoId", ns)
        video_id = video_id_el.text if video_id_el is not None else ""

        # Summary from media:description
        summary = ""
        if media_group is not None:
            desc_el = media_group.find("media:description", ns)
            if desc_el is not None and desc_el.text:
                summary = desc_el.text[:300].strip()

        # Timestamp
        ts = None
        if published_el is not None and published_el.text:
            try:
                ts = datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                pass

        # Author
        author = author_el.text if author_el is not None else feed_name

        # Views from media:statistics
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

        # Star rating
        star_rating = ""
        if media_group is not None:
            rating_el = media_group.find("media:community/media:starRating", ns)
            if rating_el is not None:
                avg = rating_el.get("average", "")
                if avg:
                    star_rating = f" | ⭐ {float(avg):.1f}"

        # min_views filter
        if self.min_views > 0 and views > 0 and views < self.min_views:
            return None

        # Category: title keyword detection > channel-name mapping > general
        category = _detect_category_from_title(title) or _channel_category(feed_name)

        # Quality score
        q_score = _quality_score(views, feed_name)

        # Build summary
        views_text = f"👁 {_format_views(views)}" if views > 0 else ""
        parts = [f"Channel: {author}"]
        if views_text:
            parts.append(views_text)
        if star_rating:
            parts.append(star_rating.strip(" |"))
        summary_prefix = " | ".join(parts)
        if summary:
            summary_prefix += f" — {summary}"

        # Tags
        tags = [
            "youtube",
            f"yt:channel:{feed_name.lower().replace(' ', '-')}",
        ]
        if is_playlist:
            tags.append("yt:playlist")
        if video_id:
            tags.append(f"yt:id:{video_id}")
        tags.append(f"yt:category:{category}")

        return Article(
            title=title,
            url=video_url,
            source=f"YouTube ({author})",
            summary=summary_prefix,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=q_score,
        )


def _channel_category(name: str) -> str:
    """Map channel names to categories."""
    mapping = {
        "tech": {"Fireship", "freeCodeCamp", "Traversy Media", "Android Developers", "Google Chrome Developers", "Computerphile"},
        "ai": {"AI Explained", "Two Minute Papers", "Bycloud", "Siraj Raval", "sentdex"},
        "science": {"Vsauce", "Veritasium", "minutephysics", "PBS Space Time", "SciShow"},
        "business": {"How Money Works", "Graham Stephan", "Patrick Boyle", "Jordan Harbinger"},
        "design": {"The Futur", "Elizabeth Filips"},
        "gaming": {"Game Maker's Toolkit"},
        "sports": {"Braille Skateboarding", "The Berrics"},
        "world": {"CNN", "Johnny Harris", "TLDR News Global"},
    }
    for cat, names in mapping.items():
        if name in names:
            return cat
    return "general"
