"""YouTube RSS source — fetches latest videos from YouTube channel RSS feeds (no API key needed)."""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

YOUTUBE_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

# Curated list of high-quality channels across categories (no API key needed)
DEFAULT_CHANNELS = {
    # Tech / CS
    "UCsBjURrPoezykLs9EqgamOA": "Fireship",
    "UCWN3xxRkmTPmbKwht9FuE5A": "Siraj Raval",
    "UCvjgXvBlbQIFgxNjLMq5FhQ": "Tom Scott",
    "UC8butISFwT-Wl7EV0hUK0BQ": "freeCodeCamp",
    "UCXv1JCOwgl2SCbB1tgLMVXg": "Traversy Media",
    # AI / ML
    "UCNJ1Ymd5yFuUPtn21xtRbbw": "AI Explained",
    "UCbfYPyITQ-7l4upoX8nvctg": "Two Minute Papers",
    "UCZHmQk67mSJgfCCTn7xBfew": "Bycloud",
    # Science
    "UC6nSFpj9HTCZ5t-N3Rm3-HA": "Vsauce",
    "UCHnyfMqiRRG1u-2MsSQLbXA": "Veritasium",
    "UCUHW94eEFW7hkUMVaZz4eDg": "minutephysics",
    "UC7_gcs09iThXybpVgjHR_7g": "PBS Space Time",
    # Business / Finance
    "UCnMn36GP_RN8OCD6mJMOxKA": "How Money Works",
    "UCV6KDgJskWaEckne5aPA0aQ": "Graham Stephan",
    "UC4xqGIZbpcedIRjA05YeBTw": "Patrick Boyle",
    # Design / Creative
    "UCKqH_9mk1waLgBiL2vT5b9g": "The Futur",
    "UCJ0-OtVpF0wOKEqT2Z1HEtA": "Elizabeth Filips",
    # News / Current Events
    "UCupvZG-5ko_eiXAupbDfxWw": "CNN",
    "UCIRYBXDze5krPDzAEOxFGVA": "Johnny Harris",
    # Gaming
    "UCNvzD7Z-g64bPXxGzaQaa4g": "Game Maker's Toolkit",
    # Skateboarding
    "UCusN3jlUbUnJGbyFwE1BfOg": "Braille Skateboarding",
    "UC9PgszLOAWhQC6orYejcJlw": "The Berrics",
}

MEDIA_NS = "http://search.yahoo.com/mrss/"
YT_NS = "http://www.youtube.com/xml/schemas/2015"


class YouTubeSource(BaseSource):
    """Fetch latest videos from YouTube channels via RSS (no API key)."""

    name = "youtube"
    timeout = 20

    def __init__(self, channels: dict | None = None, limit_per_channel: int = 5):
        self.channels = channels or DEFAULT_CHANNELS
        self.limit_per_channel = limit_per_channel

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        for channel_id, channel_name in self.channels.items():
            try:
                arts = self._fetch_channel(channel_id, channel_name)
                articles.extend(arts)
            except Exception as e:
                logger.debug(f"[YouTube] Error fetching {channel_name}: {e}")
        logger.info(f"[YouTube] Fetched {len(articles)} videos from {len(self.channels)} channels")
        return articles

    def _fetch_channel(self, channel_id: str, channel_name: str) -> List[Article]:
        url = YOUTUBE_FEED_URL.format(channel_id=channel_id)
        xml_text = self.fetch_url(url)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.debug(f"[YouTube] XML parse error for {channel_name}: {e}")
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom", "media": MEDIA_NS, "yt": YT_NS}
        entries = root.findall("atom:entry", ns)
        articles: List[Article] = []

        for entry in entries[: self.limit_per_channel]:
            try:
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                published_el = entry.find("atom:published", ns)
                media_group = entry.find("media:group", ns)

                title = title_el.text if title_el is not None else ""
                video_url = link_el.get("href", "") if link_el is not None else ""
                if not title or not video_url:
                    continue

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

                # Views from media:statistics if available
                views_text = ""
                if media_group is not None:
                    stats = media_group.find("media:community/media:statistics", ns)
                    if stats is not None:
                        views = stats.get("views", "")
                        if views:
                            views_text = f" | Views: {int(views):,}"

                articles.append(
                    Article(
                        title=title,
                        url=video_url,
                        source=f"YouTube ({channel_name})",
                        summary=f"Channel: {channel_name}{views_text}" + (f" — {summary}" if summary else ""),
                        timestamp=ts,
                        category=_channel_category(channel_name),
                        tags=["youtube", f"channel:{channel_name.lower().replace(' ', '-')}"],
                        author=channel_name,
                    )
                )
            except Exception as e:
                logger.debug(f"[YouTube] Skipping entry in {channel_name}: {e}")
                continue

        return articles


def _channel_category(name: str) -> str:
    """Map channel names to categories."""
    tech = {"Fireship", "freeCodeCamp", "Traversy Media"}
    ai = {"AI Explained", "Two Minute Papers", "Bycloud", "Siraj Raval"}
    science = {"Vsauce", "Veritasium", "minutephysics", "PBS Space Time"}
    business = {"How Money Works", "Graham Stephan", "Patrick Boyle"}
    gaming = {"Game Maker's Toolkit"}
    sports = {"Braille Skateboarding", "The Berrics"}

    if name in tech:
        return "tech"
    if name in ai:
        return "ai"
    if name in science:
        return "science"
    if name in business:
        return "business"
    if name in gaming:
        return "gaming"
    if name in sports:
        return "sports"
    return "general"
