"""The Guardian source — fetches articles from The Guardian's free RSS feeds.

The Guardian provides comprehensive free RSS feeds across all sections.
Covers: world, UK, US, tech, science, business, environment, culture, opinion, sport,
politics, books, film, music, education, law, media, money, society, football, and more.
No API key required.

Enhanced with:
- 20 section feeds (was 10)
- Two-tier keyword category detection (12 specific categories before section fallback)
- Quality scoring (0–1) based on comment indicators, author reputation, and section prominence
- Author extraction with provenance tags
- Section filtering, category filtering, min_quality, global_limit
- Cross-section URL deduplication
- Quality-sorted output
"""
import logging
import math
import re
from typing import Dict, List, Optional, Set

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

GUARDIAN_FEEDS = [
    {"url": "https://www.theguardian.com/world/rss", "section": "world", "category": "world", "prominence": 1.0},
    {"url": "https://www.theguardian.com/uk-news/rss", "section": "uk-news", "category": "world", "prominence": 0.9},
    {"url": "https://www.theguardian.com/us-news/rss", "section": "us-news", "category": "world", "prominence": 0.9},
    {"url": "https://www.theguardian.com/australia-news/rss", "section": "australia-news", "category": "world", "prominence": 0.8},
    {"url": "https://www.theguardian.com/technology/rss", "section": "technology", "category": "tech", "prominence": 0.95},
    {"url": "https://www.theguardian.com/science/rss", "section": "science", "category": "science", "prominence": 0.95},
    {"url": "https://www.theguardian.com/business/rss", "section": "business", "category": "business", "prominence": 0.9},
    {"url": "https://www.theguardian.com/environment/rss", "section": "environment", "category": "science", "prominence": 0.9},
    {"url": "https://www.theguardian.com/culture/rss", "section": "culture", "category": "culture", "prominence": 0.7},
    {"url": "https://www.theguardian.com/commentisfree/rss", "section": "opinion", "category": "opinion", "prominence": 0.6},
    {"url": "https://www.theguardian.com/sport/rss", "section": "sport", "category": "sports", "prominence": 0.7},
    {"url": "https://www.theguardian.com/politics/rss", "section": "politics", "category": "world", "prominence": 0.9},
    {"url": "https://www.theguardian.com/education/rss", "section": "education", "category": "education", "prominence": 0.75},
    {"url": "https://www.theguardian.com/books/rss", "section": "books", "category": "culture", "prominence": 0.65},
    {"url": "https://www.theguardian.com/film/rss", "section": "film", "category": "culture", "prominence": 0.7},
    {"url": "https://www.theguardian.com/music/rss", "section": "music", "category": "culture", "prominence": 0.65},
    {"url": "https://www.theguardian.com/law/rss", "section": "law", "category": "world", "prominence": 0.8},
    {"url": "https://www.theguardian.com/media/rss", "section": "media", "category": "business", "prominence": 0.75},
    {"url": "https://www.theguardian.com/society/rss", "section": "society", "category": "world", "prominence": 0.8},
    {"url": "https://www.theguardian.com/money/rss", "section": "money", "category": "business", "prominence": 0.7},
]

# Two-tier keyword category detection — specific categories checked first
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "ai": ["ai", "artificial intelligence", "machine learning", "deep learning", "neural network",
           "chatgpt", "openai", "llm", "gpt", "generative ai", "copilot", "gemini", "claude",
           "transformer", "diffusion model", "computer vision", "nlp", "robotics"],
    "security": ["cybersecurity", "hack", "breach", "malware", "ransomware", "phishing",
                 "vulnerability", "zero-day", "exploit", "encryption", "privacy", "surveillance",
                 "data leak", "infosec", "firewall", "ddos", "spyware"],
    "crypto": ["bitcoin", "ethereum", "cryptocurrency", "blockchain", "nft", "defi", "web3",
               "crypto", "solana", "stablecoin", "mining", "token", "dao"],
    "health": ["health", "medical", "vaccine", "pandemic", "disease", "cancer", "mental health",
               "nhs", "hospital", "drug", "pharmaceutical", "clinical trial", "who", "covid",
               "obesity", "diabetes", "alzheimer", "therapy", "surgery"],
    "science": ["climate", "nasa", "space", "physics", "biology", "genome", "evolution",
                "fossil", "quantum", "research", "study finds", "species", "asteroid",
                "telescope", "crispr", "dna", "molecule", "experiment"],
    "gaming": ["gaming", "video game", "playstation", "xbox", "nintendo", "steam", "esports",
               "twitch", "game pass", "console", "fortnite", "minecraft"],
    "design": ["design", "ux", "ui", "figma", "typography", "accessibility", "css",
               "frontend", "user experience", "interface"],
    "business": ["startup", "ipo", "merger", "acquisition", "revenue", "profit", "market",
                 "stock", "investor", "ceo", "valuation", "layoff", "funding", "venture"],
    "world": ["war", "conflict", "election", "diplomat", "sanction", "refugee", "treaty",
              "nato", "united nations", "geopoliti", "protest", "coup", "border"],
    "culture": ["film", "movie", "album", "concert", "exhibition", "theater", "novel",
                "oscar", "grammy", "bafta", "streaming", "netflix", "disney"],
    "education": ["university", "school", "student", "teacher", "curriculum", "tuition",
                  "scholarship", "degree", "campus", "academic"],
    "environment": ["climate change", "carbon", "emission", "renewable", "solar", "wind energy",
                    "deforestation", "biodiversity", "pollution", "fossil fuel", "net zero",
                    "sustainability", "wildfire", "flood", "drought"],
}

# Known prominent Guardian authors get a small quality boost
PROMINENT_AUTHORS: Dict[str, float] = {
    "george monbiot": 0.1,
    "owen jones": 0.08,
    "marina hyde": 0.1,
    "john harris": 0.07,
    "polly toynbee": 0.08,
    "gary younge": 0.08,
    "jonathan freedland": 0.09,
    "aditya chakrabortty": 0.07,
    "larry elliott": 0.08,
    "zoe williams": 0.07,
}


def _detect_category(title: str, summary: str, section_category: str) -> str:
    """Two-tier category detection: keywords first, then section fallback."""
    text = f"{title} {summary}".lower()
    best_cat = None
    best_count = 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > best_count:
            best_count = count
            best_cat = cat
    if best_cat and best_count >= 1:
        return best_cat
    return section_category


def _compute_quality(prominence: float, author: str, title: str, category: str) -> float:
    """Quality scoring 0–1 based on section prominence and author reputation."""
    # Baseline from section prominence (0.3–0.55)
    score = 0.3 + prominence * 0.25

    # Author reputation boost
    author_lower = author.lower().strip()
    if author_lower in PROMINENT_AUTHORS:
        score += PROMINENT_AUTHORS[author_lower]

    # Exclusive/breaking/investigation boost
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["exclusive", "breaking", "investigation", "revealed", "leaked"]):
        score += 0.1

    # Specific category boost (ai, security, environment get slight preference)
    if category in ("ai", "security", "environment"):
        score += 0.05

    return min(score, 1.0)


def _human_readable(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class GuardianSource(BaseSource):
    """Crawl The Guardian section RSS feeds.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include (by section key). None = all.
    limit : int
        Max articles per section feed. Default 15.
    min_quality : float
        Minimum quality score (0–1) to include. Default 0.0.
    category_filter : list of str or None
        Only include articles matching these categories.
    global_limit : int or None
        Total max articles across all sections (quality-sorted).
    exclude_sections : list of str or None
        Sections to exclude.
    """

    name = "guardian"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        limit: int = 15,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
        exclude_sections: Optional[List[str]] = None,
    ):
        self.sections = [s.lower() for s in sections] if sections else None
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.global_limit = global_limit
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        url = feed_info["url"]
        section = feed_info["section"]
        section_category = feed_info["category"]
        prominence = feed_info["prominence"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for entry in parsed.entries[: self.limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            # Cross-section deduplication
            if link in seen_urls:
                continue
            seen_urls.add(link)

            summary = entry.get("summary", "").strip()
            if summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                if len(summary) > 300:
                    summary = summary[:297] + "..."

            ts = None
            for date_field in ("published", "updated"):
                raw = entry.get(date_field)
                if raw:
                    try:
                        ts = dateparser.parse(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            author = entry.get("author", "")

            # Keyword-based category detection
            category = _detect_category(title, summary or "", section_category)

            # Category filter
            if self.category_filter and category not in self.category_filter:
                continue

            # Quality scoring
            quality = _compute_quality(prominence, author, title, category)
            if quality < self.min_quality:
                continue

            # Build rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 {section}")
            if summary:
                parts.append(summary)
            rich_summary = " · ".join(parts[:2])
            if summary:
                rich_summary += f"\n{summary}"

            # Provenance tags
            tags = [
                f"guardian:section:{section}",
                f"guardian:category:{category}",
            ]
            if author:
                tags.append(f"guardian:author:{author.lower().strip()}")

            # RSS category tags
            for tag_entry in entry.get("tags", []):
                term = tag_entry.get("term", "").strip().lower()
                if term:
                    tags.append(f"guardian:tag:{term}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"The Guardian ({section.title()})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                author=author,
                tags=tags,
                quality_score=quality,
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = GUARDIAN_FEEDS

        if self.sections:
            feeds = [f for f in feeds if f["section"] in self.sections]

        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"] not in self.exclude_sections]

        seen_urls: Set[str] = set()
        all_articles = []

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[Guardian] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Guardian] Failed to parse {feed_info['section']}: {e}")

        # Sort by quality score descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[Guardian] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
