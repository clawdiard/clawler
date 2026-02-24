"""Washington Post source — fetches articles from WaPo RSS feeds.

Enhanced with:
- 14 section feeds (was 7)
- Two-tier keyword category detection (12 specific categories)
- Quality scoring (0–1): section prominence × position decay + prominent author boost + category specificity
- 20 prominent WaPo journalists with reputation boost
- Cross-section URL deduplication
- Sentence-boundary summary truncation at 300 chars
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries: ✍️ author · 📰 section — description
- Provenance tags: wapo:section, wapo:category, wapo:author, wapo:prominent-author, wapo:tag
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

# ── Section feeds ──────────────────────────────────────────────────────
WAPO_FEEDS: Dict[str, dict] = {
    "national":     {"url": "https://feeds.washingtonpost.com/rss/national",              "label": "National",      "fallback_cat": "world",   "prominence": 0.55},
    "world":        {"url": "https://feeds.washingtonpost.com/rss/world",                 "label": "World",         "fallback_cat": "world",   "prominence": 0.55},
    "politics":     {"url": "https://feeds.washingtonpost.com/rss/politics",              "label": "Politics",      "fallback_cat": "world",   "prominence": 0.55},
    "business":     {"url": "https://feeds.washingtonpost.com/rss/business",              "label": "Business",      "fallback_cat": "business","prominence": 0.50},
    "technology":   {"url": "https://feeds.washingtonpost.com/rss/business/technology",   "label": "Technology",    "fallback_cat": "tech",    "prominence": 0.55},
    "climate":      {"url": "https://feeds.washingtonpost.com/rss/climate-environment",   "label": "Climate",       "fallback_cat": "environment", "prominence": 0.50},
    "opinions":     {"url": "https://feeds.washingtonpost.com/rss/opinions",              "label": "Opinions",      "fallback_cat": "culture", "prominence": 0.40},
    "health":       {"url": "https://feeds.washingtonpost.com/rss/health",                "label": "Health",        "fallback_cat": "health",  "prominence": 0.50},
    "education":    {"url": "https://feeds.washingtonpost.com/rss/education",             "label": "Education",     "fallback_cat": "education","prominence": 0.45},
    "lifestyle":    {"url": "https://feeds.washingtonpost.com/rss/lifestyle",             "label": "Lifestyle",     "fallback_cat": "culture", "prominence": 0.35},
    "entertainment":{"url": "https://feeds.washingtonpost.com/rss/entertainment",         "label": "Entertainment", "fallback_cat": "culture", "prominence": 0.35},
    "sports":       {"url": "https://feeds.washingtonpost.com/rss/sports",                "label": "Sports",        "fallback_cat": "culture", "prominence": 0.35},
    "investigations":{"url": "https://feeds.washingtonpost.com/rss/investigations",       "label": "Investigations","fallback_cat": "world",   "prominence": 0.55},
    "science":      {"url": "https://feeds.washingtonpost.com/rss/science",               "label": "Science",       "fallback_cat": "science", "prominence": 0.50},
}

# ── Prominent authors ─────────────────────────────────────────────────
PROMINENT_AUTHORS: Set[str] = {
    "david ignatius", "catherine rampell", "eugene robinson", "george will",
    "max boot", "jennifer rubin", "dana milbank", "karen tumulty",
    "robert costa", "ashley parker", "josh dawsey", "devlin barrett",
    "cat zakrzewski", "gerrit de vynck", "drew harwell", "naomi nix",
    "pranshu verma", "will oremus", "tatum hunter", "rachel lerman",
}

# ── Keyword category detection ────────────────────────────────────────
_KEYWORD_PATTERNS: Dict[str, re.Pattern] = {
    "ai":          re.compile(r"\b(ai|artificial.intelligence|machine.?learn|llm|gpt|openai|anthropic|claude|gemini|chatgpt|copilot|transformer|neural|deep.?learn|generative)\b", re.I),
    "security":    re.compile(r"\b(security|hack|breach|privacy|surveillance|encrypt|vulnerabilit|malware|ransomware|zero.?day|exploit|cyber|espionage|phishing)\b", re.I),
    "crypto":      re.compile(r"\b(crypto|bitcoin|ethereum|blockchain|defi|nft|web3|stablecoin|binance|coinbase|token)\b", re.I),
    "health":      re.compile(r"\b(health|medical|hospital|vaccine|fda|drug|cancer|disease|pandemic|mental.health|obesity|diabetes|cdc|nih|pharma)\b", re.I),
    "science":     re.compile(r"\b(science|space|nasa|climate|research|physics|biology|asteroid|rocket|mars|moon|quantum|crispr|genome|fossil)\b", re.I),
    "environment": re.compile(r"\b(environment|climate.change|global.warming|renewable|solar|wind.energy|emission|carbon|wildfire|pollution|epa|conservation)\b", re.I),
    "business":    re.compile(r"\b(acquisition|merger|layoff|ipo|funding|antitrust|lawsuit|ftc|sec|regulation|monopoly|earnings|stock|market|trade|tariff)\b", re.I),
    "world":       re.compile(r"\b(ukraine|russia|china|nato|united.nations|diplomacy|military|war|conflict|election|geopolit|sanctions|treaty|summit)\b", re.I),
    "culture":     re.compile(r"\b(movie|film|tv|streaming|netflix|disney|hbo|spotify|music|book|theater|museum|award|grammy|oscar|emmy)\b", re.I),
    "gaming":      re.compile(r"\b(game|gaming|playstation|xbox|nintendo|steam|esports|gpu|graphics.card|console)\b", re.I),
    "education":   re.compile(r"\b(education|school|university|college|student|teacher|curriculum|campus|tuition|degree|academic)\b", re.I),
    "design":      re.compile(r"\b(design|ux|ui|typography|accessibility|architecture|interior|fashion)\b", re.I),
}

# Categories that get a quality boost for specificity
_BOOSTED_CATEGORIES: Set[str] = {"ai", "security", "crypto", "environment", "health"}


def _detect_category(title: str, summary: str, tags: List[str], fallback: str) -> str:
    """Two-tier keyword category detection: specific keywords first, section fallback second."""
    text = f"{title} {summary} {' '.join(tags)}".lower()
    best_cat = None
    best_score = 0
    for cat, pattern in _KEYWORD_PATTERNS.items():
        matches = pattern.findall(text)
        if not matches:
            continue
        score = len(matches)
        # Boost specific categories over generic
        if cat in _BOOSTED_CATEGORIES:
            score += 0.5
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat if best_cat else fallback


def _truncate_at_sentence(text: str, max_len: int = 300) -> str:
    """Truncate at the last sentence boundary before max_len."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Find last sentence-ending punctuation
    for i in range(len(truncated) - 1, max(0, len(truncated) - 80), -1):
        if truncated[i] in ".!?":
            return truncated[:i + 1]
    return truncated[:max_len - 3] + "..."


class WashingtonPostSource(BaseSource):
    """Crawl Washington Post RSS feeds with quality scoring and filtering.

    Parameters
    ----------
    sections : list[str] | None
        Sections to crawl. None or ["all"] = all 14 sections.
    limit : int
        Max articles per section feed. Default 20.
    min_quality : float
        Minimum quality score threshold (0–1). Default 0.0.
    category_filter : list[str] | None
        Only return articles in these categories.
    exclude_sections : list[str] | None
        Skip these sections.
    global_limit : int | None
        Cap total articles (quality-sorted). Default None.
    """

    name = "washingtonpost"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        limit: int = 20,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.sections = sections
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = set(category_filter) if category_filter else None
        self.exclude_sections = set(s.lower() for s in exclude_sections) if exclude_sections else set()
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen_urls: Set[str] = set()

        # Determine which sections to fetch
        if self.sections and self.sections != ["all"]:
            feed_keys = [s.lower() for s in self.sections if s.lower() in WAPO_FEEDS]
        else:
            feed_keys = list(WAPO_FEEDS.keys())

        # Remove excluded sections
        feed_keys = [k for k in feed_keys if k not in self.exclude_sections]

        for section_key in feed_keys:
            feed_info = WAPO_FEEDS[section_key]
            try:
                articles = self._parse_feed(feed_info, section_key, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[WaPo] {feed_info['label']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[WaPo] Failed to parse {feed_info['label']}: {e}")

        # Apply filters
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if a.quality_score >= self.min_quality]
        if self.category_filter:
            all_articles = [a for a in all_articles if a.category in self.category_filter]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[WaPo] Total: {len(all_articles)} articles from {len(feed_keys)} sections")
        return all_articles

    def _parse_feed(self, feed_info: dict, section_key: str, seen_urls: Set[str]) -> List[Article]:
        url = feed_info["url"]
        label = feed_info["label"]
        fallback_cat = feed_info["fallback_cat"]
        prominence = feed_info["prominence"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles: List[Article] = []

        for i, entry in enumerate(parsed.entries[:self.limit]):
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            # Cross-section deduplication
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Summary with sentence-boundary truncation
            summary_raw = entry.get("summary", "").strip()
            if summary_raw:
                summary_raw = re.sub(r"<[^>]+>", "", summary_raw).strip()
            summary = _truncate_at_sentence(summary_raw) if summary_raw else ""

            # Author
            author = entry.get("author", "").strip()

            # Timestamp
            ts = None
            for date_field in ("published", "updated"):
                raw = entry.get(date_field)
                if raw:
                    try:
                        ts = dateparser.parse(raw)
                        break
                    except (ValueError, TypeError):
                        continue

            # RSS category tags
            rss_tags: List[str] = []
            for tag_dict in entry.get("tags", []):
                term = tag_dict.get("term", "").strip()
                if term:
                    rss_tags.append(term.lower())

            # Category detection
            category = _detect_category(title, summary, rss_tags, fallback_cat)

            # Quality scoring
            quality = _compute_quality(
                prominence=prominence,
                position=i,
                total=min(len(parsed.entries), self.limit),
                author=author,
                category=category,
                title=title,
                summary=summary,
            )

            # Build provenance tags
            tags = [f"wapo:section:{section_key}", f"wapo:category:{category}"]
            if author:
                tags.append(f"wapo:author:{author.lower()}")
                if author.lower() in PROMINENT_AUTHORS:
                    tags.append("wapo:prominent-author")
            for rt in rss_tags[:5]:
                tags.append(f"wapo:tag:{rt}")

            # Rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 {label}")
            if summary:
                parts.append(f"— {summary}")
            rich_summary = " · ".join(parts[:2])
            if summary:
                rich_summary += f" — {summary}"

            articles.append(Article(
                title=title,
                url=link,
                source=f"WaPo ({label})",
                summary=rich_summary,
                timestamp=ts,
                category=category,
                quality_score=quality,
                author=author,
                tags=tags,
            ))

        return articles


def _compute_quality(
    prominence: float,
    position: int,
    total: int,
    author: str,
    category: str,
    title: str,
    summary: str,
) -> float:
    """Quality score (0–1): section prominence × position decay + author + category boost."""
    # Position decay: first article gets full prominence, last gets 70%
    if total > 1:
        decay = 1.0 - 0.3 * (position / (total - 1))
    else:
        decay = 1.0
    score = prominence * decay

    # Prominent author boost
    if author.lower() in PROMINENT_AUTHORS:
        score += 0.10

    # Specific category boost
    if category in _BOOSTED_CATEGORIES:
        score += 0.08

    # Title quality signal
    word_count = len(title.split())
    if word_count >= 8:
        score += 0.03
    if word_count >= 12:
        score += 0.02

    # Summary richness
    if len(summary) > 150:
        score += 0.03

    return min(score, 1.0)
