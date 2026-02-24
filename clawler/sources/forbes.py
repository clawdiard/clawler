"""Forbes source — fetches articles from Forbes RSS feeds.

Forbes provides business, tech, entrepreneurship, and leadership news.
Free RSS feeds available at forbes.com.

Enhanced features (v10.82.0):
- 14 section feeds (was 10): added Energy, Real Estate, Small Business, Diversity & Inclusion
- Two-tier keyword category detection: 12 specific categories with 150+ keywords
  checked before section fallback
- Quality scoring (0–1): section prominence × position decay + prominent author boost
  + boosted category bonus (ai, security, crypto, environment, health)
- Prominent authors: 20 Forbes contributors (billionaire list editors, tech columnists, etc.)
- Cross-section URL deduplication
- Sentence-boundary summary truncation at 300 chars
- Filters: min_quality, category_filter, exclude_sections, global_limit with quality-sorted output
- Rich summaries: ✍️ author · 📰 section — description
- Provenance tags: forbes:section:<name>, forbes:category:<cat>, forbes:author:<name>,
  forbes:prominent-author, forbes:tag:<term>
- "all" shortcut: sections=["all"] crawls all 14 sections
"""
import logging
import math
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import feedparser
from dateutil import parser as dateparser

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# ── Section feeds ──────────────────────────────────────────────────────────
FORBES_FEEDS = [
    {"url": "https://www.forbes.com/innovation/feed2", "section": "Innovation", "prominence": 0.55},
    {"url": "https://www.forbes.com/business/feed2", "section": "Business", "prominence": 0.55},
    {"url": "https://www.forbes.com/leadership/feed2", "section": "Leadership", "prominence": 0.45},
    {"url": "https://www.forbes.com/money/feed2", "section": "Money", "prominence": 0.50},
    {"url": "https://www.forbes.com/ai/feed2", "section": "AI", "prominence": 0.55},
    {"url": "https://www.forbes.com/cybersecurity/feed2", "section": "Cybersecurity", "prominence": 0.50},
    {"url": "https://www.forbes.com/healthcare/feed2", "section": "Healthcare", "prominence": 0.45},
    {"url": "https://www.forbes.com/digital-assets/feed2", "section": "Digital Assets", "prominence": 0.45},
    {"url": "https://www.forbes.com/lifestyle/feed2", "section": "Lifestyle", "prominence": 0.35},
    {"url": "https://www.forbes.com/world/feed2", "section": "World", "prominence": 0.50},
    {"url": "https://www.forbes.com/energy/feed2", "section": "Energy", "prominence": 0.45},
    {"url": "https://www.forbes.com/real-estate/feed2", "section": "Real Estate", "prominence": 0.40},
    {"url": "https://www.forbes.com/small-business/feed2", "section": "Small Business", "prominence": 0.40},
    {"url": "https://www.forbes.com/diversity-inclusion/feed2", "section": "Diversity & Inclusion", "prominence": 0.40},
]

# Section → default category fallback (used when keyword detection finds nothing)
SECTION_CATEGORY_MAP: Dict[str, str] = {
    "Innovation": "tech",
    "Business": "business",
    "Leadership": "business",
    "Money": "business",
    "AI": "ai",
    "Cybersecurity": "security",
    "Healthcare": "health",
    "Digital Assets": "crypto",
    "Lifestyle": "culture",
    "World": "world",
    "Energy": "science",
    "Real Estate": "business",
    "Small Business": "business",
    "Diversity & Inclusion": "culture",
}

# ── Prominent Forbes contributors ─────────────────────────────────────────
PROMINENT_AUTHORS: Dict[str, float] = {
    "chase peterson-withorn": 0.10,   # Billionaires list editor
    "kerry a. dolan": 0.10,          # Billionaires list
    "robert hof": 0.08,              # Silicon Valley editor
    "alex konrad": 0.08,             # Midas List / VC coverage
    "sarah emerson": 0.08,           # Tech investigative
    "jemima mcevoy": 0.06,           # Breaking news
    "jonathan ponciano": 0.08,       # Markets / crypto
    "cyrus farivar": 0.08,           # Cybersecurity
    "thomas brewster": 0.10,         # Cybersecurity investigations
    "davide lucchese": 0.06,         # Business
    "john koetsier": 0.06,           # Innovation
    "hayley cuccinello": 0.06,       # Wealth
    "amy feldman": 0.06,             # Healthcare
    "leah rosenbaum": 0.06,          # Healthcare
    "kenrick cai": 0.08,             # AI / tech
    "richard nieva": 0.08,           # Tech
    "iain martin": 0.06,             # Billionaires
    "monica mercuri": 0.06,          # Business
    "bill conerly": 0.06,            # Economy
    "loren cecil": 0.06,             # Real estate
}

# ── Two-tier keyword category detection ────────────────────────────────────
_CATEGORY_KEYWORDS: List[Tuple[str, re.Pattern]] = [
    ("ai", re.compile(
        r"\b(artificial.intelligence|machine.learn\w*|deep.learn\w*|neural.net\w*|"
        r"llm|large.language|gpt|openai|anthropic|claude|gemini|copilot|"
        r"generative.ai|gen.?ai|chatbot|transformer|diffusion|"
        r"computer.vision|nlp|natural.language|reinforcement.learn\w*|"
        r"ai.?model|ai.?agent|foundation.model|multimodal)\b", re.I)),
    ("security", re.compile(
        r"\b(cyber.?secur\w*|data.breach|ransomware|malware|phishing|"
        r"zero.?day|vulnerabilit\w*|exploit\w*|cve-?\d*|infosec|"
        r"hack(?:ed|ing|er)|ddos|threat.actor|apt\d*|encryption|"
        r"identity.theft|fraud|scam|dark.?web|password|credential)\b", re.I)),
    ("crypto", re.compile(
        r"\b(bitcoin|ethereum|crypto.?currenc\w*|blockchain|web3|"
        r"defi|nft|token\w*|stablecoin|solana|cardano|"
        r"digital.asset\w*|mining|wallet|exchange|binance|coinbase)\b", re.I)),
    ("health", re.compile(
        r"\b(health.?care|medical|pharma\w*|biotech\w*|clinical.trial|"
        r"fda|drug|vaccine|hospital|patient|diagnosis|treatment|"
        r"mental.health|wellness|telemedicine|genomic\w*|crispr|"
        r"cancer|diabetes|obesity|pandemic|epidemic)\b", re.I)),
    ("science", re.compile(
        r"\b(research|scientist\w*|physics|chemistry|biology|"
        r"climate|environment\w*|renewable|solar|wind.energy|"
        r"space|nasa|quantum|nuclear|fusion|battery|ev\b|"
        r"electric.vehicle|carbon|emission\w*|sustainab\w*)\b", re.I)),
    ("business", re.compile(
        r"\b(startup|funding|ipo|acquisition|merger|layoff|"
        r"revenue|valuation|vc|venture.capital|series.[a-d]|"
        r"unicorn|billion\w*|ceo|executive|board.?of|"
        r"private.equity|hedge.fund|wall.street|stock.market)\b", re.I)),
    ("world", re.compile(
        r"\b(geopolitic\w*|diplomac\w*|sanction\w*|nato|"
        r"united.nations|trade.war|tariff|immigration|"
        r"election|government|policy|regulation|congress|"
        r"european.union|china|russia|middle.east)\b", re.I)),
    ("culture", re.compile(
        r"\b(entertainment|movie|film|music|art|book|"
        r"fashion|luxury|travel|food|restaurant|"
        r"celebrity|award|oscar|grammy|netflix|"
        r"sport\w*|nfl|nba|soccer|football|olympic)\b", re.I)),
    ("education", re.compile(
        r"\b(education|university|college|student|"
        r"professor|academic|scholarship|degree|"
        r"online.learn\w*|edtech|curriculum|campus)\b", re.I)),
    ("design", re.compile(
        r"\b(design|ux|ui|user.experience|product.design|"
        r"architect\w*|interior|graphic|creative|brand)\b", re.I)),
    ("gaming", re.compile(
        r"\b(gaming|video.?game|esport\w*|playstation|xbox|"
        r"nintendo|steam|twitch|game.?dev|metaverse)\b", re.I)),
    ("environment", re.compile(
        r"\b(climate.change|global.warming|carbon.footprint|"
        r"deforestation|biodiversity|endangered|pollution|"
        r"recycling|circular.economy|clean.energy|green)\b", re.I)),
]

# Boosted categories get +0.08 quality bonus
_BOOSTED_CATEGORIES = {"ai", "security", "crypto", "environment", "health"}


def _detect_category(title: str, summary: str, section: str) -> str:
    """Two-tier detection: specific keywords first, then section fallback."""
    text = f"{title} {summary}"
    for cat, pattern in _CATEGORY_KEYWORDS:
        if pattern.search(text):
            return cat
    return SECTION_CATEGORY_MAP.get(section, "tech")


def _truncate_at_sentence(text: str, max_len: int = 300) -> str:
    """Truncate at last sentence boundary before max_len."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Find last sentence boundary
    for sep in (". ", "! ", "? "):
        idx = truncated.rfind(sep)
        if idx > max_len * 0.4:
            return truncated[:idx + 1]
    return truncated.rsplit(" ", 1)[0] + "…"


def _human_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class ForbesSource(BaseSource):
    """Crawl Forbes RSS feeds with enhanced quality scoring and categorization.

    Parameters
    ----------
    sections : list of str or None
        Which sections to include. ``["all"]`` = all sections. None = all.
    limit : int
        Max articles per section feed. Default 15.
    min_quality : float
        Skip articles below this quality (0.0–1.0). Default 0.0.
    category_filter : list of str or None
        Only return articles matching these categories. Default None (all).
    exclude_sections : list of str or None
        Skip these sections. Default None.
    global_limit : int or None
        Max total articles returned (quality-sorted). Default None.
    """

    name = "forbes"

    def __init__(
        self,
        sections: Optional[List[str]] = None,
        limit: int = 15,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.sections = sections
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = [c.lower() for c in category_filter] if category_filter else None
        self.exclude_sections = [s.lower() for s in exclude_sections] if exclude_sections else None
        self.global_limit = global_limit

    def _get_feeds(self) -> List[dict]:
        """Resolve which feeds to crawl."""
        feeds = FORBES_FEEDS
        if self.sections:
            if "all" in [s.lower() for s in self.sections]:
                return feeds
            allowed = {s.lower() for s in self.sections}
            feeds = [f for f in feeds if f["section"].lower() in allowed]
        if self.exclude_sections:
            feeds = [f for f in feeds if f["section"].lower() not in self.exclude_sections]
        return feeds

    def _compute_quality(
        self, section: str, prominence: float, position: int,
        author: str, category: str
    ) -> float:
        """Compute quality score (0–1)."""
        # Base: section prominence (0.35–0.55)
        q = prominence

        # Position decay: first article gets full score, decays to 70%
        decay = max(0.70, 1.0 - (position * 0.02))
        q *= decay

        # Prominent author boost (0–0.10)
        if author:
            q += PROMINENT_AUTHORS.get(author.lower(), 0.0)

        # Boosted category bonus
        if category in _BOOSTED_CATEGORIES:
            q += 0.08

        return min(1.0, round(q, 3))

    def _parse_feed(self, feed_info: dict, seen_urls: Set[str]) -> List[Article]:
        """Parse a single Forbes RSS feed."""
        url = feed_info["url"]
        section = feed_info["section"]
        prominence = feed_info["prominence"]

        content = self.fetch_url(url)
        if not content:
            return []

        parsed = feedparser.parse(content)
        articles = []

        for position, entry in enumerate(parsed.entries[:self.limit]):
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            # Cross-section URL deduplication
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Summary extraction + HTML stripping + sentence-boundary truncation
            raw_summary = entry.get("summary", "").strip()
            if raw_summary:
                raw_summary = re.sub(r"<[^>]+>", "", raw_summary).strip()
                raw_summary = _truncate_at_sentence(raw_summary)

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

            author = entry.get("author", "").strip()

            # Two-tier category detection
            category = _detect_category(title, raw_summary, section)

            # Quality scoring
            quality = self._compute_quality(section, prominence, position, author, category)

            # Apply filters
            if self.min_quality and quality < self.min_quality:
                continue
            if self.category_filter and category not in self.category_filter:
                continue

            # Rich summary
            parts = []
            if author:
                parts.append(f"✍️ {author}")
            parts.append(f"📰 Forbes {section}")
            if raw_summary:
                parts.append(f"— {raw_summary}")
            summary = " · ".join(parts[:2])
            if raw_summary:
                summary += f" — {raw_summary}"

            # Provenance tags
            tags = [
                f"forbes:section:{section.lower().replace(' ', '-')}",
                f"forbes:category:{category}",
            ]
            if author:
                tags.append(f"forbes:author:{author.lower()}")
                if author.lower() in PROMINENT_AUTHORS:
                    tags.append("forbes:prominent-author")

            # Extract RSS category tags
            for tag_entry in entry.get("tags", []):
                term = tag_entry.get("term", "").strip()
                if term:
                    tags.append(f"forbes:tag:{term.lower()}")

            articles.append(Article(
                title=title,
                url=link,
                source=f"Forbes ({section})",
                summary=summary,
                timestamp=ts,
                category=category,
                quality_score=quality,
                author=author,
                tags=tags,
            ))

        return articles

    def crawl(self) -> List[Article]:
        feeds = self._get_feeds()
        all_articles: List[Article] = []
        seen_urls: Set[str] = set()

        for feed_info in feeds:
            try:
                articles = self._parse_feed(feed_info, seen_urls)
                all_articles.extend(articles)
                logger.info(f"[Forbes] {feed_info['section']}: {len(articles)} articles")
            except Exception as e:
                logger.warning(f"[Forbes] Failed to parse {feed_info['section']}: {e}")

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score, reverse=True)

        # Apply global limit
        if self.global_limit and len(all_articles) > self.global_limit:
            all_articles = all_articles[:self.global_limit]

        logger.info(f"[Forbes] Total: {len(all_articles)} articles from {len(feeds)} sections")
        return all_articles
