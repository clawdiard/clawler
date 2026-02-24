"""TechRadar source — consumer tech, reviews, and buying guides.

Enhanced features:
- 6 section feeds (was 3): added audio, gaming, AI/computing sections
- Quality scoring (0–1) based on feed prominence × position decay + author boost
- Two-tier keyword category detection (8 specific categories)
- Prominent journalist detection (10+ TechRadar writers)
- Cross-feed URL deduplication
- Filters: min_quality, category_filter, global_limit
- Rich summaries with ✍️ author · 📱 feed · description
- Provenance tags: tr:feed, tr:category, tr:author, tr:prominent-author
"""
import logging
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

TECHRADAR_FEEDS = [
    {"url": "https://www.techradar.com/rss", "feed": "All", "default_category": "tech", "prominence": 0.48},
    {"url": "https://www.techradar.com/rss/news/computing", "feed": "Computing", "default_category": "tech", "prominence": 0.50},
    {"url": "https://www.techradar.com/rss/news/phone-and-communications", "feed": "Mobile", "default_category": "mobile", "prominence": 0.48},
    {"url": "https://www.techradar.com/rss/news/audio", "feed": "Audio", "default_category": "audio", "prominence": 0.42},
    {"url": "https://www.techradar.com/rss/news/gaming", "feed": "Gaming", "default_category": "gaming", "prominence": 0.44},
    {"url": "https://www.techradar.com/rss/news/software", "feed": "Software", "default_category": "tech", "prominence": 0.46},
]

# Keyword category detection
_CATEGORY_RULES = [
    ("ai", re.compile(r"\b(ai|artificial.?intelligence|machine.?learn|chatgpt|copilot|gemini|openai|llm|generative)\b", re.I)),
    ("security", re.compile(r"\b(security|vpn|antivirus|malware|hack|breach|ransomware|privacy|password|phishing|zero.?day)\b", re.I)),
    ("gaming", re.compile(r"\b(game|gaming|ps5|xbox|nintendo|gpu|graphics.?card|steam|rtx|radeon|esport)\b", re.I)),
    ("mobile", re.compile(r"\b(iphone|android|samsung|pixel|phone|smartphone|tablet|ipad|wearable|watch|galaxy)\b", re.I)),
    ("audio", re.compile(r"\b(headphone|earbuds?|speaker|soundbar|audio|noise.?cancel|bluetooth|hi.?fi|dac|amp)\b", re.I)),
    ("streaming", re.compile(r"\b(netflix|disney|hbo|stream|apple.?tv|prime.?video|hulu|paramount|peacock)\b", re.I)),
    ("smart_home", re.compile(r"\b(smart.?home|alexa|google.?home|ring|nest|iot|smart.?speaker|hub|zigbee|matter)\b", re.I)),
    ("photo", re.compile(r"\b(camera|dslr|mirrorless|lens|photo|lightroom|photoshop|drone|gopro)\b", re.I)),
]

# Prominent TechRadar writers
PROMINENT_AUTHORS: Dict[str, str] = {
    "lance ulanoff": "tech",
    "john loeffler": "computing",
    "allisa james": "gaming",
    "matt hanson": "computing",
    "mackenzie frazier": "audio",
    "axel springer": "mobile",
    "darren allan": "computing",
    "mike moore": "security",
    "cat ellis": "security",
    "becky scarrott": "audio",
    "james peckham": "mobile",
    "gerald lynch": "tech",
}

PROMINENT_AUTHOR_BOOST = 0.06
BOOSTED_CATEGORIES: Set[str] = {"ai", "security"}
BOOST_AMOUNT = 0.07


def _detect_category(title: str, summary: str) -> Optional[str]:
    text = f"{title} {summary}"
    for cat, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return cat
    return None


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


class TechRadarSource(BaseSource):
    """Fetch articles from TechRadar's RSS feeds.

    Parameters
    ----------
    limit : int
        Max articles per feed. Default 20.
    global_limit : int | None
        Max total articles (quality-sorted). None = unlimited.
    min_quality : float
        Minimum quality score threshold (0–1). Default 0.0.
    category_filter : list[str] | None
        Only return articles matching these categories.
    """

    name = "techradar"

    def __init__(
        self,
        limit: int = 20,
        global_limit: Optional[int] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.limit = limit
        self.global_limit = global_limit
        self.min_quality = min_quality
        self.category_filter = {c.lower() for c in category_filter} if category_filter else None

    def _parse_feed(self, feed_info: dict, seen: Set[str]) -> List[Article]:
        feed_url = feed_info["url"]
        feed_name = feed_info["feed"]
        default_cat = feed_info["default_category"]
        base_prominence = feed_info["prominence"]

        xml_text = self.fetch_url(feed_url)
        if not xml_text:
            return []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[TechRadar] XML parse error for {feed_name}: {e}")
            return []

        ns_dc = {"dc": "http://purl.org/dc/elements/1.1/"}
        articles: List[Article] = []

        for idx, item in enumerate(root.findall(".//item")[:self.limit]):
            try:
                title_el = item.find("title")
                link_el = item.find("link")

                title = (title_el.text or "").strip() if title_el is not None else ""
                url = (link_el.text or "").strip() if link_el is not None else ""

                if not title or not url or url in seen:
                    continue
                seen.add(url)

                # Description
                summary = ""
                desc_el = item.find("description")
                if desc_el is not None and desc_el.text:
                    summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

                # Author
                author = ""
                creator_el = item.find("dc:creator", ns_dc)
                if creator_el is not None and creator_el.text:
                    author = creator_el.text.strip()

                # Timestamp
                ts = None
                pub_el = item.find("pubDate")
                if pub_el is not None and pub_el.text:
                    ts = _parse_date(pub_el.text)

                # Category: keywords first, then feed default
                detected = _detect_category(title, summary)
                category = detected or default_cat

                # Quality scoring: prominence × position decay + boosts
                position_decay = 1.0 / (1.0 + math.log1p(idx))
                quality = base_prominence * position_decay

                # Prominent author boost
                is_prominent = False
                if author:
                    author_lower = author.lower()
                    for pa_name in PROMINENT_AUTHORS:
                        if pa_name in author_lower:
                            quality += PROMINENT_AUTHOR_BOOST
                            is_prominent = True
                            break

                # Boosted category bonus
                if category in BOOSTED_CATEGORIES:
                    quality += BOOST_AMOUNT

                quality = min(quality, 1.0)

                # Filters
                if quality < self.min_quality:
                    continue
                if self.category_filter and category not in self.category_filter:
                    continue

                # Rich summary
                parts = []
                if author:
                    parts.append(f"✍️ {author}")
                parts.append(f"📱 {feed_name}")
                rich_summary = " · ".join(parts)
                if summary:
                    rich_summary += f" — {summary}"

                # Tags
                tags = [
                    f"tr:feed:{feed_name.lower()}",
                    f"tr:category:{category}",
                ]
                if author:
                    tags.append(f"tr:author:{author.lower().replace(' ', '-')}")
                if is_prominent:
                    tags.append("tr:prominent-author")
                for cat_el in item.findall("category"):
                    if cat_el.text:
                        tags.append(f"tr:{cat_el.text.strip().lower()}")

                articles.append(Article(
                    title=title,
                    url=url,
                    source=f"TechRadar ({feed_name})",
                    summary=rich_summary,
                    timestamp=ts,
                    category=category,
                    quality_score=quality,
                    tags=tags,
                    author=author,
                ))
            except Exception as e:
                logger.debug(f"[TechRadar] Skipping item: {e}")

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen: Set[str] = set()

        for feed_info in TECHRADAR_FEEDS:
            try:
                articles = self._parse_feed(feed_info, seen)
                all_articles.extend(articles)
                logger.info(f"[TechRadar] {feed_info['feed']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[TechRadar] Failed to parse {feed_info['feed']}: {e}")

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        # Global limit
        if self.global_limit and len(all_articles) > self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[TechRadar] Total: {len(all_articles)} articles")
        return all_articles
