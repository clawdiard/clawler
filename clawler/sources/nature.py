"""Nature News source — high-impact science journalism from nature.com RSS (no key needed).

Enhanced v10.58.0:
- 18 journal feeds (was 5): added Medicine, Energy, Neuroscience, Genetics, Physics, Electronics,
  Sustainability, Communications, Reviews, Immunology, Methods, Catalysis, Food
- Two-tier keyword category detection: 12 specific categories with 120+ keywords
- Quality scoring (0–1): journal impact tier × position decay + keyword specificity boost
- Cross-feed URL deduplication
- Filters: min_quality, category_filter, exclude_sections, global_limit
- Rich summaries: ✍️ author · 📰 journal · description (sentence-boundary truncation)
- Provenance tags: nature:journal:<name>, nature:category:<cat>, nature:author:<name>, nature:doi:<id>
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

# ---------------------------------------------------------------------------
# Journal feeds — grouped by impact tier for quality scoring
# ---------------------------------------------------------------------------

NATURE_FEEDS = [
    # Tier 1 — flagship + highest-impact
    {"url": "https://www.nature.com/nature.rss", "section": "nature", "tier": 1},
    {"url": "https://www.nature.com/nm.rss", "section": "medicine", "tier": 1},
    {"url": "https://www.nature.com/natmachintell.rss", "section": "machine-intelligence", "tier": 1},
    {"url": "https://www.nature.com/nclimate.rss", "section": "climate", "tier": 1},
    {"url": "https://www.nature.com/neuro.rss", "section": "neuroscience", "tier": 1},
    {"url": "https://www.nature.com/ng.rss", "section": "genetics", "tier": 1},
    # Tier 2 — high-impact specialty
    {"url": "https://www.nature.com/nbt.rss", "section": "biotech", "tier": 2},
    {"url": "https://www.nature.com/nnano.rss", "section": "nanotech", "tier": 2},
    {"url": "https://www.nature.com/nenergy.rss", "section": "energy", "tier": 2},
    {"url": "https://www.nature.com/nphys.rss", "section": "physics", "tier": 2},
    {"url": "https://www.nature.com/s41928.rss", "section": "electronics", "tier": 2},
    {"url": "https://www.nature.com/ni.rss", "section": "immunology", "tier": 2},
    # Tier 3 — specialty / newer journals
    {"url": "https://www.nature.com/s41893.rss", "section": "sustainability", "tier": 3},
    {"url": "https://www.nature.com/ncomms.rss", "section": "communications", "tier": 3},
    {"url": "https://www.nature.com/s43586.rss", "section": "reviews-methods", "tier": 3},
    {"url": "https://www.nature.com/s41929.rss", "section": "catalysis", "tier": 3},
    {"url": "https://www.nature.com/s43016.rss", "section": "food", "tier": 3},
    {"url": "https://www.nature.com/s41586.rss", "section": "research", "tier": 1},
]

# ---------------------------------------------------------------------------
# Section → default category mapping
# ---------------------------------------------------------------------------

SECTION_CATEGORY: Dict[str, str] = {
    "nature": "science",
    "research": "science",
    "medicine": "health",
    "machine-intelligence": "ai",
    "climate": "environment",
    "neuroscience": "science",
    "genetics": "health",
    "biotech": "science",
    "nanotech": "science",
    "energy": "environment",
    "physics": "science",
    "electronics": "tech",
    "immunology": "health",
    "sustainability": "environment",
    "communications": "science",
    "reviews-methods": "science",
    "catalysis": "science",
    "food": "health",
}

# ---------------------------------------------------------------------------
# Keyword → specific category (checked before section fallback)
# ---------------------------------------------------------------------------

KEYWORD_CATEGORIES: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "machine learning", "deep learning", "neural network",
        "large language model", "llm", "gpt", "transformer", "reinforcement learning",
        "computer vision", "natural language", "generative ai", "diffusion model",
        "foundation model", "chatbot", "robotics", "autonomous",
    ],
    "security": [
        "cybersecurity", "malware", "ransomware", "vulnerability", "exploit",
        "encryption", "privacy", "surveillance", "biosecurity", "biodefense",
        "pathogen", "pandemic preparedness", "dual-use",
    ],
    "crypto": [
        "cryptocurrency", "blockchain", "bitcoin", "ethereum", "defi",
        "web3", "smart contract", "token",
    ],
    "health": [
        "cancer", "tumor", "clinical trial", "drug", "therapy", "vaccine",
        "diagnosis", "patient", "disease", "medical", "pharmaceutical",
        "crispr", "gene therapy", "gene editing", "immunotherapy",
        "antibiotic", "antiviral", "mental health", "obesity", "diabetes",
        "alzheimer", "parkinson", "dementia", "heart", "cardio",
    ],
    "environment": [
        "climate change", "global warming", "carbon", "emission", "renewable",
        "solar", "wind energy", "biodiversity", "extinction", "deforestation",
        "ocean", "pollution", "plastic", "sustainability", "ecosystem",
        "conservation", "drought", "flood", "wildfire", "ice sheet",
    ],
    "science": [
        "quantum", "physics", "astronomy", "astrophysics", "black hole",
        "exoplanet", "dark matter", "dark energy", "particle", "higgs",
        "superconductor", "fusion", "fission", "telescope", "mars",
        "moon", "space", "cosmos", "evolution", "fossil", "dinosaur",
        "geology", "chemistry", "molecule", "protein", "dna", "rna",
        "genome", "cell", "neuron", "brain", "photosynthesis",
    ],
    "business": [
        "startup", "investment", "venture capital", "market", "economic",
        "industry", "patent", "regulation", "policy", "funding",
        "ipo", "acquisition", "merger",
    ],
    "world": [
        "geopolitics", "conflict", "humanitarian", "refugee", "migration",
        "sanction", "diplomacy", "treaty", "un ", "united nations",
        "who ", "world health",
    ],
    "education": [
        "education", "university", "student", "academic", "curriculum",
        "scholarship", "peer review", "open access", "publishing",
    ],
    "design": [
        "biomimicry", "biodesign", "synthetic biology", "tissue engineering",
        "3d printing", "nanomaterial", "metamaterial",
    ],
    "gaming": [
        "video game", "gaming", "esport", "virtual reality", "vr ",
        "augmented reality", "ar ", "metaverse",
    ],
    "culture": [
        "ethics", "society", "philosophy", "history", "archaeology",
        "anthropology", "psychology", "behavior", "cognition",
    ],
}

# Tier → base quality score
TIER_BASE: Dict[int, float] = {1: 0.80, 2: 0.65, 3: 0.50}

# Categories that get a quality boost when detected
BOOSTED_CATEGORIES: Set[str] = {"ai", "security", "environment", "health"}

# ---------------------------------------------------------------------------
# XML parsing helpers
# ---------------------------------------------------------------------------

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TAG_RE = {
    "title": re.compile(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", re.DOTALL),
    "link": re.compile(r"<link>(.*?)</link>"),
    "description": re.compile(
        r"<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>",
        re.DOTALL,
    ),
    "pubDate": re.compile(r"<pubDate>(.*?)</pubDate>"),
    "creator": re.compile(
        r"<dc:creator><!\[CDATA\[(.*?)\]\]></dc:creator>|<dc:creator>(.*?)</dc:creator>",
        re.DOTALL,
    ),
    "doi": re.compile(r"<prism:doi>(.*?)</prism:doi>|doi\.org/(10\.\d{4,}/[^\s<\"]+)"),
    "category": re.compile(
        r"<category><!\[CDATA\[(.*?)\]\]></category>|<category>(.*?)</category>",
        re.DOTALL,
    ),
}

_DOI_FROM_URL = re.compile(r"doi\.org/(10\.\d{4,}/[^\s<\"?#]+)")


def _extract(pattern, text: str) -> str:
    m = pattern.search(text)
    if not m:
        return ""
    return next((g for g in m.groups() if g is not None), "").strip()


def _extract_all(pattern, text: str) -> List[str]:
    results = []
    for m in pattern.finditer(text):
        val = next((g for g in m.groups() if g is not None), "").strip()
        if val:
            results.append(val)
    return results


def _truncate_at_sentence(text: str, max_len: int = 280) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Try to cut at sentence boundary
    for sep in (". ", "! ", "? "):
        idx = truncated.rfind(sep)
        if idx > max_len * 0.4:
            return truncated[: idx + 1]
    # Fall back to word boundary
    idx = truncated.rfind(" ")
    if idx > max_len * 0.4:
        return truncated[:idx] + "…"
    return truncated + "…"


def _detect_category(title: str, rss_categories: List[str], section: str) -> str:
    """Two-tier category detection: keywords first, then section fallback."""
    search_text = (title + " " + " ".join(rss_categories)).lower()

    # Tier 1: specific keyword match
    scores: Dict[str, int] = {}
    for cat, keywords in KEYWORD_CATEGORIES.items():
        for kw in keywords:
            if kw in search_text:
                scores[cat] = scores.get(cat, 0) + 1

    if scores:
        # Prefer specific over generic 'science'
        best = max(scores, key=lambda c: (scores[c], c != "science"))
        if best != "science" or not any(c != "science" for c in scores):
            return best

    # Tier 2: section fallback
    return SECTION_CATEGORY.get(section, "science")


def _compute_quality(tier: int, position: int, total: int, category: str) -> float:
    """Quality score 0–1: tier base × position decay + category boost."""
    base = TIER_BASE.get(tier, 0.50)
    # Position decay: first item gets full score, last gets ~70% of base
    if total > 1:
        decay = 1.0 - 0.3 * (position / (total - 1))
    else:
        decay = 1.0
    score = base * decay
    # Boost for high-value categories
    if category in BOOSTED_CATEGORIES:
        score = min(1.0, score + 0.08)
    return round(score, 3)


class NatureSource(BaseSource):
    """Fetch latest research articles from Nature journals RSS feeds.

    Params:
        feeds: list of feed dicts (url, section, tier). Defaults to 18 journals.
        limit: max articles per feed (default 15).
        min_quality: minimum quality score 0–1 (default 0).
        category_filter: list of categories to include (default: all).
        exclude_sections: list of journal sections to skip.
        global_limit: max total articles returned (quality-sorted).
    """

    name = "nature"

    def __init__(
        self,
        feeds=None,
        limit: int = 15,
        min_quality: float = 0,
        category_filter: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        global_limit: Optional[int] = None,
    ):
        self.feeds = feeds or NATURE_FEEDS
        self.limit = limit
        self.min_quality = min_quality
        self.category_filter = set(category_filter) if category_filter else None
        self.exclude_sections = set(exclude_sections) if exclude_sections else set()
        self.global_limit = global_limit

    def _parse_feed(self, feed_url: str, section: str, tier: int) -> List[Article]:
        xml = self.fetch_url(feed_url)
        if not xml:
            return []

        articles: List[Article] = []
        items = _ITEM_RE.findall(xml)
        total = min(len(items), self.limit)

        for idx, item_xml in enumerate(items[: self.limit]):
            try:
                title = _extract(_TAG_RE["title"], item_xml)
                url = _extract(_TAG_RE["link"], item_xml)
                if not title or not url:
                    continue

                # Description
                raw_desc = _extract(_TAG_RE["description"], item_xml)
                desc = re.sub(r"<[^>]+>", "", raw_desc).strip()
                desc = _truncate_at_sentence(desc)

                # Author
                author = _extract(_TAG_RE["creator"], item_xml)

                # DOI
                doi = _extract(_TAG_RE["doi"], item_xml)
                if not doi:
                    doi_m = _DOI_FROM_URL.search(url)
                    if doi_m:
                        doi = doi_m.group(1)

                # RSS categories
                rss_cats = _extract_all(_TAG_RE["category"], item_xml)

                # Timestamp
                ts = None
                pub_date = _extract(_TAG_RE["pubDate"], item_xml)
                if pub_date:
                    try:
                        ts = parsedate_to_datetime(pub_date)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # Category detection
                category = _detect_category(title, rss_cats, section)

                # Quality score
                quality = _compute_quality(tier, idx, total, category)

                # Build summary
                parts = []
                if author:
                    parts.append(f"✍️ {author}")
                journal_label = section.replace("-", " ").title()
                parts.append(f"📰 Nature {journal_label}")
                if desc:
                    parts.append(desc)
                summary = " · ".join(parts[:2])
                if desc:
                    summary += f" — {desc}"

                # Provenance tags
                tags = [
                    f"nature:journal:{section}",
                    f"nature:category:{category}",
                    f"nature:tier:{tier}",
                ]
                if author:
                    safe_author = author.lower().replace(" ", "-")[:50]
                    tags.append(f"nature:author:{safe_author}")
                if doi:
                    tags.append(f"nature:doi:{doi}")
                for rc in rss_cats[:5]:
                    tags.append(f"nature:tag:{rc.lower().replace(' ', '-')[:40]}")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Nature ({journal_label})",
                        summary=summary,
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=author,
                        quality_score=quality,
                    )
                )
            except Exception as e:
                logger.debug(f"[Nature] Skipping item: {e}")
                continue

        return articles

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen_urls: Set[str] = set()

        for feed in self.feeds:
            section = feed["section"]
            if section in self.exclude_sections:
                continue
            try:
                articles = self._parse_feed(feed["url"], section, feed.get("tier", 3))
                for a in articles:
                    if a.url not in seen_urls:
                        seen_urls.add(a.url)
                        all_articles.append(a)
            except Exception as e:
                logger.warning(f"[Nature] Failed to fetch {section}: {e}")

        # Apply filters
        if self.min_quality > 0:
            all_articles = [a for a in all_articles if (a.quality_score or 0) >= self.min_quality]

        if self.category_filter:
            all_articles = [a for a in all_articles if a.category in self.category_filter]

        # Sort by quality descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        if self.global_limit:
            all_articles = all_articles[: self.global_limit]

        logger.info(
            f"[Nature] Fetched {len(all_articles)} articles from "
            f"{len([f for f in self.feeds if f['section'] not in self.exclude_sections])} journal feeds"
        )
        return all_articles
