"""CNBC source — fetches articles from CNBC RSS feeds.

CNBC provides high-quality business, financial markets, and technology news.
Free RSS feeds are available at cnbc.com.

Enhanced with:
- 12 section feeds (Top News, Finance, Technology, Media, Earnings, World,
  Politics, Health, Real Estate, Energy, Small Business, Investing)
- Two-tier keyword category detection (150+ keywords across 12 categories)
- Quality scoring (0–1): section prominence × position decay + keyword specificity
  + prominent author boost
- 18 prominent CNBC journalists with reputation scores
- Cross-section URL deduplication
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries: ✍️ author · 📰 section — description (sentence-boundary truncation)
- Provenance tags: cnbc:section, cnbc:category, cnbc:author, cnbc:prominent-author, cnbc:tag
- Quality-sorted output
"""
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# ── Section feeds ──────────────────────────────────────────────────────────────

CNBC_FEEDS: Dict[str, Dict] = {
    "top_news":      {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147", "label": "Top News",      "category": "business", "prominence": 0.55},
    "finance":       {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", "label": "Finance",       "category": "business", "prominence": 0.55},
    "technology":    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910", "label": "Technology",    "category": "tech",     "prominence": 0.50},
    "media":         {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069", "label": "Media",         "category": "culture",  "prominence": 0.45},
    "earnings":      {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "label": "Earnings",      "category": "business", "prominence": 0.50},
    "world":         {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114","label": "World",         "category": "world",    "prominence": 0.50},
    "politics":      {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000113", "label": "Politics",      "category": "world",    "prominence": 0.50},
    "health":        {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000108", "label": "Health & Science","category": "health", "prominence": 0.45},
    "real_estate":   {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000115", "label": "Real Estate",   "category": "business", "prominence": 0.40},
    "energy":        {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19836768", "label": "Energy",        "category": "business", "prominence": 0.45},
    "small_business":{"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=44877279", "label": "Small Business","category": "business", "prominence": 0.40},
    "investing":     {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135", "label": "Investing",     "category": "business", "prominence": 0.50},
}

# ── Prominent CNBC authors ────────────────────────────────────────────────────

PROMINENT_AUTHORS: Dict[str, float] = {
    "jim cramer": 0.12,
    "andrew ross sorkin": 0.12,
    "david faber": 0.10,
    "carl quintanilla": 0.08,
    "sara eisen": 0.08,
    "becky quick": 0.08,
    "scott wapner": 0.08,
    "kate rooney": 0.08,
    "mackenzie sigalos": 0.08,
    "robert frank": 0.08,
    "steve kovach": 0.08,
    "kif leswing": 0.10,
    "ari levy": 0.08,
    "christina farr": 0.08,
    "meg tirrell": 0.08,
    "jordan novet": 0.08,
    "jessica bursztynsky": 0.06,
    "hayden field": 0.08,
}

# ── Keyword category detection ────────────────────────────────────────────────

_CATEGORY_RULES: List[Tuple[str, re.Pattern]] = [
    ("ai",          re.compile(r"\b(ai|artificial.intelligence|machine.?learn|llm|gpt|openai|anthropic|claude|gemini|chatgpt|copilot|transformer|neural|deep.?learn|midjourney|stable.?diffusion)\b", re.I)),
    ("security",    re.compile(r"\b(security|hack|breach|privacy|surveillance|encrypt|vulnerabilit|malware|ransomware|zero.?day|exploit|cyberattack|spyware|phishing|data.?leak)\b", re.I)),
    ("crypto",      re.compile(r"\b(bitcoin|ethereum|crypto|blockchain|web3|defi|nft|stablecoin|binance|coinbase|solana|token|altcoin)\b", re.I)),
    ("health",      re.compile(r"\b(health|pharma|fda|drug|vaccine|hospital|biotech|clinical.?trial|medical|cancer|diabetes|mental.?health|telehealth|healthcare)\b", re.I)),
    ("science",     re.compile(r"\b(science|nasa|spacex|climate|quantum|genome|research|physics|biology|asteroid|rocket|mars|moon|crispr|fusion)\b", re.I)),
    ("environment", re.compile(r"\b(environment|climate.?change|renewable|solar|wind.?energy|ev|electric.?vehicle|carbon|emissions|green.?energy|sustainability|esg)\b", re.I)),
    ("world",       re.compile(r"\b(geopolitic|china|russia|ukraine|europe|nato|sanction|tariff|trade.?war|diplomat|middle.?east|conflict|summit)\b", re.I)),
    ("business",    re.compile(r"\b(earnings|revenue|ipo|acquisition|merger|layoff|valuation|bankruptcy|profit|gdp|inflation|interest.?rate|fed|recession|market|stock|wall.?street)\b", re.I)),
    ("culture",     re.compile(r"\b(movie|film|streaming|netflix|disney|spotify|music|podcast|youtube|tiktok|social.media|entertainment)\b", re.I)),
    ("gaming",      re.compile(r"\b(game|gaming|playstation|xbox|nintendo|steam|esports|gpu)\b", re.I)),
    ("design",      re.compile(r"\b(design|ux|ui|figma|creative|typography|branding)\b", re.I)),
    ("education",   re.compile(r"\b(education|university|student|campus|tuition|college|edtech|school)\b", re.I)),
]

# Categories that get a quality boost when detected by keyword
_BOOSTED_CATEGORIES = {"ai", "security", "crypto", "environment", "health"}


def _detect_category(title: str, summary: str, section_category: str) -> str:
    """Two-tier detection: keyword-specific first, then section fallback."""
    text = f"{title} {summary}"
    best_cat = None
    best_count = 0
    for cat, pattern in _CATEGORY_RULES:
        matches = pattern.findall(text)
        if matches and len(matches) > best_count:
            best_cat = cat
            best_count = len(matches)
    return best_cat if best_cat else section_category


def _truncate_at_sentence(text: str, max_len: int = 300) -> str:
    """Truncate text at a sentence boundary near max_len."""
    if len(text) <= max_len:
        return text
    # Find last sentence-ending punctuation before max_len
    truncated = text[:max_len]
    for sep in (". ", "! ", "? "):
        idx = truncated.rfind(sep)
        if idx > max_len * 0.5:
            return truncated[:idx + 1]
    return truncated[:max_len - 3] + "..."


def _compute_quality(
    section_key: str,
    category: str,
    section_category: str,
    position: int,
    author: str,
) -> float:
    """Quality score (0–1): prominence × position decay + keyword boost + author."""
    feed_info = CNBC_FEEDS.get(section_key, {})
    base = feed_info.get("prominence", 0.40)

    # Position decay (first article = full score, later articles fade)
    position_factor = 1.0 / (1.0 + 0.04 * position)
    score = base * position_factor

    # Keyword-detected specific category bonus
    if category != section_category and category in _BOOSTED_CATEGORIES:
        score += 0.10
    elif category != section_category:
        score += 0.05

    # Prominent author boost
    author_boost = PROMINENT_AUTHORS.get(author.lower().strip(), 0.0)
    score += author_boost

    return round(min(1.0, score), 3)


class CNBCSource(BaseSource):
    """Fetch articles from CNBC RSS feeds with quality scoring.

    Parameters
    ----------
    feeds : list of str or None
        Section keys to crawl. Default: ["top_news"]. Use ["all"] for all sections.
        Options: top_news, finance, technology, media, earnings, world,
                 politics, health, real_estate, energy, small_business, investing.
    limit : int
        Max articles per feed. Default 25.
    min_quality : float
        Minimum quality score (0–1). Default 0.0.
    category_filter : list of str or None
        Only include articles in these categories.
    exclude_sections : list of str or None
        Exclude these sections from crawling.
    global_limit : int or None
        Max total articles (quality-sorted). None = no limit.
    """

    name = "cnbc"

    def __init__(
        self,
        feeds: Optional[List[str]] = None,
        limit: int = 25,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.cnbc_feeds = feeds or ["top_news"]
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = set(s.lower() for s in exclude_sections) if exclude_sections else set()
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        seen_urls: Set[str] = set()
        all_articles: List[Article] = []

        # Resolve "all" → every section
        if "all" in self.cnbc_feeds:
            active_sections = list(CNBC_FEEDS.keys())
        else:
            active_sections = self.cnbc_feeds

        # Apply exclusions
        active_sections = [s for s in active_sections if s not in self.exclude_sections]

        for section_key in active_sections:
            feed_info = CNBC_FEEDS.get(section_key)
            if not feed_info:
                logger.warning(f"[CNBC] Unknown feed: {section_key}")
                continue
            try:
                content = self.fetch_url(feed_info["url"])
                if not content:
                    continue
                parsed = self._parse_feed(content, section_key, feed_info, seen_urls)
                all_articles.extend(parsed)
                logger.info(f"[CNBC] {feed_info['label']}: {len(parsed)} articles")
            except Exception as e:
                logger.warning(f"[CNBC] Failed to fetch {section_key}: {e}")

        # Apply filters
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if (a.quality_score or 0) >= self.min_quality]

        if self.category_filter:
            all_articles = [a for a in all_articles if a.category in self.category_filter]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        # Global limit
        if self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[CNBC] Total: {len(all_articles)} articles from {len(active_sections)} section(s)")
        return all_articles

    def _parse_feed(
        self,
        content: str,
        section_key: str,
        feed_info: Dict,
        seen: Set[str],
    ) -> List[Article]:
        """Parse a single CNBC RSS feed into articles."""
        parsed = feedparser.parse(content)
        articles: List[Article] = []

        for position, entry in enumerate(parsed.entries[:self.limit]):
            try:
                article = self._parse_entry(entry, section_key, feed_info, position, seen)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[CNBC] Skipping entry in {section_key}: {e}")

        return articles

    def _parse_entry(
        self,
        entry,
        section_key: str,
        feed_info: Dict,
        position: int,
        seen: Set[str],
    ) -> Optional[Article]:
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()
        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Summary with sentence-boundary truncation
        summary = entry.get("summary", "").strip()
        if summary:
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            summary = _truncate_at_sentence(summary, 300)

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

        # Category detection
        section_category = feed_info["category"]
        category = _detect_category(title, summary, section_category)

        # Quality scoring
        quality = _compute_quality(section_key, category, section_category, position, author)

        # Rich summary
        label = feed_info["label"]
        parts = []
        if author:
            parts.append(f"✍️ {author}")
        parts.append(f"📰 {label}")
        header = " · ".join(parts)
        rich_summary = f"{header} — {summary}" if summary else header

        # Provenance tags
        tags = [
            f"cnbc:section:{section_key}",
            f"cnbc:category:{category}",
        ]
        if author:
            author_lower = author.lower().strip()
            tags.append(f"cnbc:author:{author_lower}")
            if author_lower in PROMINENT_AUTHORS:
                tags.append("cnbc:prominent-author")

        # RSS category tags
        for cat_entry in entry.get("tags", []):
            term = cat_entry.get("term", "").strip()
            if term:
                tags.append(f"cnbc:tag:{term.lower()}")

        return Article(
            title=title,
            url=url,
            source=f"CNBC ({label})",
            summary=rich_summary,
            timestamp=ts,
            category=category,
            tags=tags,
            author=author,
            quality_score=quality,
        )
