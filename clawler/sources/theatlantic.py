"""The Atlantic source — fetches articles from theatlantic.com RSS feeds.

Prestigious American magazine covering politics, culture, technology,
health, and international affairs since 1857. Known for longform
journalism and deep analysis.
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# The Atlantic RSS feeds by section
FEEDS = {
    "latest": "https://www.theatlantic.com/feed/all/",
    "best-of": "https://www.theatlantic.com/feed/best-of/",
    "politics": "https://www.theatlantic.com/feed/channel/politics/",
    "technology": "https://www.theatlantic.com/feed/channel/technology/",
    "ideas": "https://www.theatlantic.com/feed/channel/ideas/",
    "science": "https://www.theatlantic.com/feed/channel/science/",
    "health": "https://www.theatlantic.com/feed/channel/health/",
    "culture": "https://www.theatlantic.com/feed/channel/entertainment/",
    "business": "https://www.theatlantic.com/feed/channel/business/",
    "international": "https://www.theatlantic.com/feed/channel/international/",
    "family": "https://www.theatlantic.com/feed/channel/family/",
    "education": "https://www.theatlantic.com/feed/channel/education/",
}

# Prominent Atlantic authors for quality scoring
PROMINENT_AUTHORS = frozenset({
    "derek thompson", "anne applebaum", "george packer", "david frum",
    "adam serwer", "robinson meyer", "conor friedersdorf", "ed yong",
    "charlie warzel", "megan garber", "franklin foer", "ta-nehisi coates",
    "james fallows", "jennifer senior", "caitlin dickerson",
})

# Keyword-to-category mappings
_CATEGORY_KEYWORDS = {
    "tech": ["\\bai\\b", "artificial intelligence", "algorithm", "software", "silicon valley",
             "\\btech\\b", "internet", "social media", "startup", "crypto", "blockchain"],
    "science": ["science", "research", "study", "climate", "space", "nasa", "evolution",
                "biology", "physics", "pandemic", "virus", "vaccine"],
    "world": ["ukraine", "china", "russia", "europe", "middle east", "nato",
              "geopolitics", "foreign policy", "war", "diplomacy", "refugee"],
    "business": ["economy", "inflation", "market", "wall street", "labor",
                 "unemployment", "housing", "fed", "trade", "supply chain"],
    "culture": ["book", "film", "movie", "tv", "music", "art", "culture",
                "review", "literary", "novel", "theater", "poetry"],
    "security": ["security", "cybersecurity", "surveillance", "privacy",
                 "intelligence", "espionage", "fbi", "cia", "nsa"],
    "investigative": ["investigation", "expose", "revealed", "documents show",
                      "exclusive", "whistleblower", "corruption"],
}


class TheAtlanticSource(BaseSource):
    """Fetch articles from The Atlantic's RSS feeds."""

    name = "theatlantic"

    def __init__(self, sections: Optional[List[str]] = None, limit: int = 30):
        self.sections = sections or list(FEEDS.keys())
        self.limit = limit

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen: Set[str] = set()

        for section in self.sections:
            feed_url = FEEDS.get(section)
            if not feed_url:
                continue
            try:
                xml_text = self.fetch_url(feed_url)
                if xml_text:
                    section_articles = self._parse_feed(xml_text, section, seen)
                    articles.extend(section_articles)
            except Exception as e:
                logger.warning(f"[TheAtlantic] Failed to fetch {section}: {e}")

        articles.sort(key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        logger.info(f"[TheAtlantic] Fetched {len(articles)} articles across {len(self.sections)} sections")
        return articles[:self.limit]

    def _parse_feed(self, xml_text: str, section: str, seen: Set[str]) -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[TheAtlantic] XML parse error for {section}: {e}")
            return articles

        channel = root.find("channel")
        if channel is None:
            return articles

        for item in channel.findall("item"):
            try:
                article = self._parse_item(item, section, seen)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[TheAtlantic] Skipping item in {section}: {e}")

        return articles

    def _parse_item(self, item, section: str, seen: Set[str]) -> Optional[Article]:
        title_el = item.find("title")
        link_el = item.find("link")

        title = (title_el.text or "").strip() if title_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Summary
        summary = ""
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Author
        author = ""
        # dc:creator namespace
        for ns_prefix in ["{http://purl.org/dc/elements/1.1/}", ""]:
            author_el = item.find(f"{ns_prefix}creator")
            if author_el is not None and author_el.text:
                author = author_el.text.strip()
                break
        if not author:
            author_el = item.find("author")
            if author_el is not None and author_el.text:
                author = author_el.text.strip()

        # Timestamp
        ts = None
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            ts = _parse_date(pub_el.text)

        # Tags
        tags = [f"atlantic:{section}"]
        for cat_el in item.findall("category"):
            if cat_el.text:
                tags.append(f"atlantic:{cat_el.text.strip().lower()}")

        # Category detection
        category = _detect_category(title, summary, section)

        # Quality scoring: boost prominent authors
        quality_bonus = 0.05 if author.lower() in PROMINENT_AUTHORS else 0.0

        article = Article(
            title=title,
            url=url,
            source=f"The Atlantic ({section.replace('-', ' ').title()})",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
        )
        return article


def _detect_category(title: str, summary: str, section: str) -> str:
    """Detect article category from title, summary, and section."""
    # Section-based defaults
    section_map = {
        "politics": "world", "technology": "tech", "science": "science",
        "health": "science", "business": "business", "culture": "culture",
        "international": "world", "education": "culture",
    }
    default = section_map.get(section, "general")

    text = (title + " " + summary).lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.startswith("\\b"):
                # Regex pattern for short words
                if re.search(kw, text):
                    return cat
            elif kw in text:
                return cat

    return default


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    from email.utils import parsedate_to_datetime
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
