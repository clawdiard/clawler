"""The Register source — snarky tech journalism via RSS (no key needed).

v10.16.0 enhancements:
- Multi-section fetching with configurable section selection
- Quality scoring (0–1) based on comment count + section prominence
- Two-tier keyword category detection (specific → section fallback)
- Author byline extraction + provenance tags
- Section/category/comment filters
- Global limit with quality-sorted output
- Enriched summaries with 📰 section + 💬 comments + ✍️ author
"""
import logging
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# The Register section RSS feeds (all public)
REGISTER_FEEDS = [
    {"url": "https://www.theregister.com/headlines.atom", "section": "headlines"},
    {"url": "https://www.theregister.com/security/headlines.atom", "section": "security"},
    {"url": "https://www.theregister.com/software/headlines.atom", "section": "software"},
    {"url": "https://www.theregister.com/networks/headlines.atom", "section": "networks"},
    {"url": "https://www.theregister.com/data_centre/headlines.atom", "section": "data_centre"},
    {"url": "https://www.theregister.com/on_prem/headlines.atom", "section": "on_prem"},
    {"url": "https://www.theregister.com/offbeat/headlines.atom", "section": "offbeat"},
    {"url": "https://www.theregister.com/science/headlines.atom", "section": "science"},
    {"url": "https://www.theregister.com/bootnotes/headlines.atom", "section": "bootnotes"},
    {"url": "https://www.theregister.com/emergent_tech/headlines.atom", "section": "emergent_tech"},
    {"url": "https://www.theregister.com/public_sector/headlines.atom", "section": "public_sector"},
    {"url": "https://www.theregister.com/personal_tech/headlines.atom", "section": "personal_tech"},
]

# Section → default category fallback
_SECTION_CATEGORY = {
    "headlines": "tech",
    "security": "security",
    "software": "tech",
    "networks": "tech",
    "data_centre": "tech",
    "on_prem": "tech",
    "offbeat": "culture",
    "science": "science",
    "bootnotes": "culture",
    "emergent_tech": "ai",
    "public_sector": "world",
    "personal_tech": "tech",
}

# Keyword → specific category (checked before section fallback)
_KEYWORD_CATEGORIES = {
    "ai": ["ai", "artificial intelligence", "machine learning", "llm", "chatgpt", "openai",
            "neural", "deep learning", "gpt", "copilot", "generative", "transformer",
            "large language", "diffusion", "stable diffusion", "midjourney", "anthropic",
            "gemini", "claude", "llama", "mistral"],
    "security": ["security", "vulnerability", "exploit", "hack", "ransomware", "malware",
                  "phishing", "breach", "cve", "zero-day", "botnet", "ddos", "encryption",
                  "infosec", "cyberattack", "backdoor", "apt", "patch tuesday"],
    "crypto": ["crypto", "bitcoin", "ethereum", "blockchain", "nft", "defi", "web3",
               "stablecoin", "binance", "coinbase"],
    "science": ["science", "research", "study finds", "experiment", "physics", "biology",
                "chemistry", "quantum", "nasa", "space", "mars", "satellite", "telescope",
                "crispr", "genome", "climate", "fusion"],
    "health": ["health", "medical", "hospital", "patient", "vaccine", "drug", "fda",
               "clinical trial", "disease", "pandemic", "nhs"],
    "business": ["acquisition", "merger", "ipo", "revenue", "profit", "layoff", "antitrust",
                 "regulation", "lawsuit", "fine", "gdpr", "ftc", "sec filing", "market share"],
    "world": ["government", "legislation", "congress", "parliament", "eu", "china",
              "election", "policy", "sanction", "military", "war", "geopolitics"],
    "gaming": ["gaming", "game", "playstation", "xbox", "nintendo", "steam", "gpu",
               "graphics card", "nvidia", "amd", "geforce"],
    "design": ["design", "ux", "user experience", "accessibility", "a11y", "interface"],
}

_TAG_RE = re.compile(r"<[^>]+>")
_COMMENT_RE = re.compile(r"(\d+)\s*comments?", re.IGNORECASE)


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _parse_atom_date(date_str: str) -> Optional[datetime]:
    """Parse ISO 8601 / Atom date string."""
    if not date_str:
        return None
    try:
        cleaned = date_str.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        pass
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None


def _detect_category(title: str, summary: str, section: str) -> str:
    """Two-tier category detection: keywords first, then section fallback."""
    text = f"{title} {summary}".lower()
    best_cat = None
    best_count = 0
    for cat, keywords in _KEYWORD_CATEGORIES.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > best_count:
            best_count = count
            best_cat = cat
    if best_cat and best_count >= 1:
        return best_cat
    return _SECTION_CATEGORY.get(section, "tech")


def _compute_quality(comment_count: int, section: str) -> float:
    """Quality score 0–1 based on comments + editorial prominence.

    Baseline 0.35 (Register = curated editorial).
    50 comments ≈ 0.65, 200+ ≈ 0.85.
    Security/science sections get a slight boost.
    """
    base = 0.35
    if comment_count > 0:
        base += 0.5 * (math.log10(1 + comment_count) / math.log10(500))
    # Section prominence boost
    if section in ("security", "science", "emergent_tech"):
        base += 0.05
    return min(1.0, max(0.0, base))


def _format_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _extract_comment_count(summary_html: str) -> int:
    """Try to extract comment count from RSS content."""
    m = _COMMENT_RE.search(summary_html)
    return int(m.group(1)) if m else 0


class TheRegisterSource(BaseSource):
    """Crawl The Register via Atom feeds.

    Config options:
        sections (list[str]): Sections to fetch. Default: all.
        min_comments (int): Skip articles with fewer comments. Default: 0.
        min_quality (float): Minimum quality score. Default: 0.0.
        category_filter (list[str]): Only return these categories.
        section_filter (list[str]): Only fetch these sections.
        global_limit (int): Max articles returned. Default: unlimited.
    """

    name = "theregister"

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        sections = self.config.get("sections") or self.config.get("section_filter")
        min_comments = self.config.get("min_comments", 0)
        min_quality = self.config.get("min_quality", 0.0)
        category_filter = self.config.get("category_filter")
        global_limit = self.config.get("global_limit")

        if category_filter and isinstance(category_filter, str):
            category_filter = [category_filter]

        feeds = REGISTER_FEEDS
        if sections:
            section_set = set(s.lower() for s in sections)
            feeds = [f for f in feeds if f["section"] in section_set]

        for feed_info in feeds:
            url = feed_info["url"]
            section = feed_info["section"]
            text = self.fetch_url(url)
            if not text:
                continue

            try:
                entries = self._parse_atom(text)
            except Exception as e:
                logger.warning(f"[theregister] Failed to parse {section} feed: {e}")
                continue

            for entry in entries:
                link = entry.get("link", "").strip()
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                title = _strip_html(entry.get("title", "")).strip()
                raw_summary = entry.get("summary", "")
                summary = _strip_html(raw_summary).strip()
                if not title:
                    continue

                comment_count = _extract_comment_count(raw_summary)
                if comment_count < min_comments:
                    continue

                published = _parse_atom_date(entry.get("updated") or entry.get("published", ""))
                author = entry.get("author", "")

                category = _detect_category(title, summary, section)

                if category_filter and category not in category_filter:
                    continue

                quality = _compute_quality(comment_count, section)
                if quality < min_quality:
                    continue

                # Build enriched summary
                parts = []
                if author:
                    parts.append(f"✍️ {author}")
                parts.append(f"📰 {section}")
                if comment_count > 0:
                    parts.append(f"💬 {_format_count(comment_count)}")
                prefix = " · ".join(parts)
                enriched = f"{prefix} — {summary[:400]}" if summary else prefix

                # Provenance tags
                tags = [
                    f"register:section:{section}",
                    f"register:category:{category}",
                ]
                if author:
                    tags.append(f"register:author:{author}")
                if comment_count > 0:
                    tags.append("register:has-discussion")

                articles.append(Article(
                    title=title,
                    url=link,
                    source="theregister",
                    summary=enriched,
                    timestamp=published,
                    author=author,
                    category=category,
                    quality_score=quality,
                    tags=tags,
                ))

        # Sort by quality (best first) and apply global limit
        articles.sort(key=lambda a: a.quality_score, reverse=True)
        if global_limit and global_limit > 0:
            articles = articles[:global_limit]

        logger.info(f"[theregister] Collected {len(articles)} articles from {len(feeds)} feeds")
        return articles

    @staticmethod
    def _parse_atom(text: str) -> List[dict]:
        """Minimal Atom feed parser — no external deps."""
        entries = []
        parts = re.split(r"<entry[^>]*>", text)
        for part in parts[1:]:
            end = part.find("</entry>")
            if end >= 0:
                part = part[:end]

            entry = {}
            m = re.search(r"<title[^>]*>(.*?)</title>", part, re.DOTALL)
            if m:
                entry["title"] = _strip_html(m.group(1))

            m = re.search(r'<link[^>]*href="([^"]+)"', part)
            if m:
                entry["link"] = m.group(1)

            for tag in ("summary", "content"):
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", part, re.DOTALL)
                if m:
                    entry["summary"] = m.group(1)  # keep raw HTML for comment extraction
                    break

            for tag in ("updated", "published"):
                m = re.search(rf"<{tag}>(.*?)</{tag}>", part)
                if m:
                    entry[tag] = m.group(1).strip()

            m = re.search(r"<author>\s*<name>(.*?)</name>", part, re.DOTALL)
            if m:
                entry["author"] = m.group(1).strip()

            if entry.get("title") and entry.get("link"):
                entries.append(entry)

        return entries
