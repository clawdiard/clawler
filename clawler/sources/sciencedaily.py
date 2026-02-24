"""ScienceDaily source — latest science research news from sciencedaily.com.

Enhanced features:
- 10 section feeds (was 7): added plants_animals, fossils_ruins, earth_climate split
- Quality scoring (0–1) based on section prominence × position decay
- Keyword category detection (8 specific science subcategories)
- Cross-section URL deduplication
- Filters: min_quality, category_filter, global_limit
- Rich summaries with 🔬 section · description
- Provenance tags: sciencedaily:section, sciencedaily:category
"""
import logging
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Set

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# ScienceDaily RSS feeds by section
SCIENCEDAILY_FEEDS = [
    {"url": "https://www.sciencedaily.com/rss/top.xml", "section": "Top Stories", "default_category": "science", "prominence": 0.55},
    {"url": "https://www.sciencedaily.com/rss/computers_math.xml", "section": "Computers & Math", "default_category": "tech", "prominence": 0.50},
    {"url": "https://www.sciencedaily.com/rss/matter_energy.xml", "section": "Physics", "default_category": "physics", "prominence": 0.48},
    {"url": "https://www.sciencedaily.com/rss/space_time.xml", "section": "Space", "default_category": "space", "prominence": 0.50},
    {"url": "https://www.sciencedaily.com/rss/health_medicine.xml", "section": "Health", "default_category": "health", "prominence": 0.48},
    {"url": "https://www.sciencedaily.com/rss/mind_brain.xml", "section": "Neuroscience", "default_category": "neuroscience", "prominence": 0.48},
    {"url": "https://www.sciencedaily.com/rss/earth_climate.xml", "section": "Earth & Climate", "default_category": "environment", "prominence": 0.48},
    {"url": "https://www.sciencedaily.com/rss/plants_animals.xml", "section": "Biology", "default_category": "biology", "prominence": 0.45},
    {"url": "https://www.sciencedaily.com/rss/fossils_ruins.xml", "section": "Paleontology", "default_category": "science", "prominence": 0.42},
    {"url": "https://www.sciencedaily.com/rss/living_well.xml", "section": "Living Well", "default_category": "health", "prominence": 0.40},
]

# Section prominence for scoring
SECTION_PROMINENCE: Dict[str, float] = {f["section"]: f["prominence"] for f in SCIENCEDAILY_FEEDS}

# Keyword → category mapping
KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": ["artificial intelligence", "machine learning", "neural network", "deep learning",
           "language model", "chatbot", "robot", "algorithm", "computer vision"],
    "space": ["nasa", "mars", "moon", "asteroid", "exoplanet", "telescope", "satellite",
              "space station", "rocket", "cosmic", "galaxy", "black hole", "james webb"],
    "health": ["cancer", "vaccine", "clinical trial", "fda", "drug", "therapy",
               "patient", "disease", "treatment", "diabetes", "alzheimer", "heart"],
    "neuroscience": ["brain", "neuron", "cognitive", "memory", "consciousness",
                     "mental health", "depression", "anxiety", "sleep", "dementia"],
    "environment": ["climate change", "global warming", "carbon", "emission", "renewable",
                    "biodiversity", "deforestation", "ocean", "wildfire", "pollution",
                    "coral reef", "ecosystem", "drought", "flooding"],
    "physics": ["quantum", "particle", "photon", "fusion", "superconductor",
                "gravitational", "dark matter", "dark energy", "laser", "plasma"],
    "biology": ["gene", "dna", "rna", "crispr", "cell", "protein", "evolution",
                "species", "genome", "mutation", "bacteria", "virus", "microbiome"],
    "tech": ["computer", "software", "semiconductor", "chip", "data", "network",
             "cybersecurity", "blockchain", "quantum computing", "5g"],
}

# Boosted categories
BOOSTED_CATEGORIES: Set[str] = {"ai", "space", "environment"}
BOOST_AMOUNT = 0.06

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TAG_RE = {
    "title": re.compile(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", re.DOTALL),
    "link": re.compile(r"<link>(.*?)</link>"),
    "description": re.compile(
        r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>",
        re.DOTALL,
    ),
    "pubDate": re.compile(r"<pubDate>(.*?)</pubDate>"),
}


def _extract(pattern, text):
    m = pattern.search(text)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


def _detect_category(title: str, summary: str) -> Optional[str]:
    text = f"{title} {summary}".lower()
    for cat, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return None


class ScienceDailySource(BaseSource):
    """Fetch latest research news from ScienceDaily RSS feeds.

    Parameters
    ----------
    feeds : list[dict] | None
        Override default feeds.
    limit : int
        Max articles per feed. Default 15.
    global_limit : int | None
        Max total articles (quality-sorted). None = unlimited.
    min_quality : float
        Minimum quality score threshold (0–1). Default 0.0.
    category_filter : list[str] | None
        Only return articles matching these categories.
    """

    name = "sciencedaily"

    def __init__(
        self,
        feeds=None,
        limit: int = 15,
        global_limit: Optional[int] = None,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
    ):
        self.feeds = feeds or SCIENCEDAILY_FEEDS
        self.limit = limit
        self.global_limit = global_limit
        self.min_quality = min_quality
        self.category_filter = {c.lower() for c in category_filter} if category_filter else None

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        feed_url = feed_info["url"]
        section = feed_info["section"]
        default_cat = feed_info.get("default_category", "science")
        base_prominence = feed_info.get("prominence", 0.45)

        xml = self.fetch_url(feed_url)
        if not xml:
            return []

        articles: List[Article] = []
        items = _ITEM_RE.findall(xml)

        for idx, item_xml in enumerate(items[:self.limit]):
            try:
                title = _extract(_TAG_RE["title"], item_xml)
                url = _extract(_TAG_RE["link"], item_xml)
                if not title or not url:
                    continue

                # Dedup across sections
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                summary_raw = _extract(_TAG_RE["description"], item_xml)
                summary = re.sub(r"<[^>]+>", "", summary_raw).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

                ts = None
                pub_date = _extract(_TAG_RE["pubDate"], item_xml)
                if pub_date:
                    try:
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # Category: keywords first, then section default
                detected = _detect_category(title, summary)
                category = detected or default_cat

                # Quality scoring: prominence × position decay
                position_decay = 1.0 / (1.0 + math.log1p(idx))
                quality = base_prominence * position_decay

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
                rich_summary = f"🔬 {section}"
                if summary:
                    rich_summary += f" — {summary}"

                # Provenance tags
                tags = [
                    f"sciencedaily:section:{section.lower().replace(' ', '-').replace('&', 'and')}",
                    f"sciencedaily:category:{category}",
                ]

                articles.append(Article(
                    title=title,
                    url=url,
                    source=f"ScienceDaily ({section})",
                    summary=rich_summary,
                    timestamp=ts,
                    category=category,
                    quality_score=quality,
                    tags=tags,
                ))
            except Exception as e:
                logger.debug(f"[ScienceDaily] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen_urls: Set[str] = set()

        for feed_info in self.feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[ScienceDaily] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[ScienceDaily] Failed to fetch {feed_info['section']}: {e}")

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        # Global limit
        if self.global_limit and len(all_articles) > self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[ScienceDaily] Total: {len(all_articles)} articles from {len(self.feeds)} sections")
        return all_articles
