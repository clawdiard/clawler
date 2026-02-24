"""Engadget source — fetches articles from Engadget RSS feed.

Consumer tech, gadgets, gaming, and entertainment coverage.

Enhanced features:
- Multi-section feeds (5 feeds: main, AI, gaming, entertainment, science)
- Quality scoring (0–1) based on feed prominence × position decay + author boost
- Two-tier keyword category detection (8 specific categories)
- Prominent journalist detection (12+ Engadget writers) with reputation boost
- Cross-feed URL deduplication
- Filters: min_quality, category_filter, global_limit
- Rich summaries with ✍️ author · 📡 feed · description
- Provenance tags: engadget:feed, engadget:category, engadget:author, engadget:prominent-author
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

# Engadget RSS feeds — main + section-specific
ENGADGET_FEEDS = [
    {"url": "https://www.engadget.com/rss.xml", "feed": "Main", "default_category": "tech", "prominence": 0.50},
    {"url": "https://www.engadget.com/ai/rss.xml", "feed": "AI", "default_category": "ai", "prominence": 0.52},
    {"url": "https://www.engadget.com/gaming/rss.xml", "feed": "Gaming", "default_category": "gaming", "prominence": 0.45},
    {"url": "https://www.engadget.com/entertainment/rss.xml", "feed": "Entertainment", "default_category": "entertainment", "prominence": 0.40},
    {"url": "https://www.engadget.com/science/rss.xml", "feed": "Science", "default_category": "science", "prominence": 0.48},
]

# Keyword-based category detection (specific → general)
_CATEGORY_RULES = [
    ("ai", re.compile(r"\b(ai|llm|gpt|openai|anthropic|machine.?learn|chatbot|copilot|gemini|claude|midjourney|stable.?diffusion|language.?model|deep.?learn)\b", re.I)),
    ("security", re.compile(r"\b(security|hack|breach|malware|ransomware|privacy|surveillance|phishing|zero.?day|exploit|vulnerability|encryption)\b", re.I)),
    ("gaming", re.compile(r"\b(game|gaming|playstation|xbox|nintendo|steam|console|esport|gpu|rtx|radeon|ps5)\b", re.I)),
    ("mobile", re.compile(r"\b(iphone|android|samsung|pixel|smartphone|ipad|tablet|wearable|apple.?watch|galaxy)\b", re.I)),
    ("science", re.compile(r"\b(nasa|space|climate|research|study|satellite|mars|moon|telescope|quantum|crispr)\b", re.I)),
    ("automotive", re.compile(r"\b(ev|electric.?vehicle|tesla|rivian|self.?driving|autonomous|lidar|charging.?station)\b", re.I)),
    ("entertainment", re.compile(r"\b(stream|netflix|disney|movie|film|tv|show|music|spotify|apple.?tv|hbo|youtube)\b", re.I)),
    ("audio", re.compile(r"\b(headphone|earbuds?|speaker|soundbar|audio|podcast|bluetooth.?audio|noise.?cancel)\b", re.I)),
    ("tech", re.compile(r"\b(laptops?|computers?|pc|chips?|processors?|intel|amd|nvidia|software|apps?|robots?|drones?|gadgets?|reviews?|displays?|monitors?|keyboards?|mouse|routers?|wi.?fi|usb|tech)\b", re.I)),
]

# Prominent Engadget writers with beat expertise
PROMINENT_AUTHORS: Dict[str, str] = {
    "cherlynn low": "mobile",
    "karissa bell": "tech",
    "igor bonifacic": "tech",
    "kris holt": "gaming",
    "mat smith": "tech",
    "sam rutherford": "mobile",
    "billy steele": "audio",
    "steve dent": "science",
    "devindra hardawar": "computing",
    "jessica conditt": "gaming",
    "mariella moon": "tech",
    "daniel cooper": "tech",
}

PROMINENT_AUTHOR_BOOST = 0.06
BOOSTED_CATEGORIES: Set[str] = {"ai", "security", "science"}
BOOST_AMOUNT = 0.07


def _detect_category(title: str, summary: str) -> Optional[str]:
    text = f"{title} {summary}"
    for cat, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return cat
    return None


def _parse_rss_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class EngadgetSource(BaseSource):
    """Fetch articles from Engadget RSS feeds.

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

    name = "engadget"

    def __init__(
        self,
        limit: int = 20,
        global_limit: Optional[int] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
    ):
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
            logger.warning(f"[Engadget] XML parse error for {feed_name}: {e}")
            return []

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        articles: List[Article] = []

        for idx, item in enumerate(root.findall(".//item")[:self.limit]):
            try:
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                pubdate_el = item.find("pubDate")
                creator_el = item.find("dc:creator", ns)

                title = (title_el.text or "").strip() if title_el is not None else ""
                url = (link_el.text or "").strip() if link_el is not None else ""

                if not title or not url or url in seen:
                    continue
                seen.add(url)

                summary = ""
                if desc_el is not None and desc_el.text:
                    summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
                    if len(summary) > 300:
                        summary = summary[:297] + "..."

                author = (creator_el.text or "").strip() if creator_el is not None else ""
                ts = _parse_rss_date(pubdate_el.text if pubdate_el is not None else None)

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

                # Build rich summary
                parts = []
                if author:
                    parts.append(f"✍️ {author}")
                parts.append(f"📡 {feed_name}")
                rich_summary = " · ".join(parts)
                if summary:
                    rich_summary += f" — {summary}"

                # Provenance tags
                tags = [
                    f"engadget:feed:{feed_name.lower()}",
                    f"engadget:category:{category}",
                ]
                if author:
                    tags.append(f"engadget:author:{author.lower().replace(' ', '-')}")
                if is_prominent:
                    tags.append("engadget:prominent-author")
                for cat_el in item.findall("category"):
                    if cat_el.text:
                        tags.append(f"engadget:{cat_el.text.strip().lower()}")

                articles.append(Article(
                    title=title,
                    url=url,
                    source=f"Engadget ({feed_name})",
                    summary=rich_summary,
                    timestamp=ts,
                    category=category,
                    quality_score=quality,
                    tags=tags,
                    author=author,
                ))
            except Exception as e:
                logger.debug(f"[Engadget] Skipping item: {e}")

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen: Set[str] = set()

        for feed_info in ENGADGET_FEEDS:
            try:
                articles = self._parse_feed(feed_info, seen)
                all_articles.extend(articles)
                logger.info(f"[Engadget] {feed_info['feed']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Engadget] Failed to parse {feed_info['feed']}: {e}")

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        # Global limit
        if self.global_limit and len(all_articles) > self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[Engadget] Total: {len(all_articles)} articles")
        return all_articles
