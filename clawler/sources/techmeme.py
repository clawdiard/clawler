"""TechMeme source — curated tech news river via RSS (no key needed).

Enhanced v10.6.0:
- Source publication extraction from RSS summary HTML (e.g. "via NYT", "via Verge")
- Related articles count from RSS summary (counts linked sources in discussion)
- Prominence-based quality scoring: related_count drives score (more discussion = higher)
- Category-specific keywords expanded: added ai, crypto, health, design, gaming, education
- Provenance tags: techmeme:source:<publication>, techmeme:category:<cat>, techmeme:topic:<tag>
- min_quality filter to skip low-prominence articles
- category_filter to restrict output categories
- global_limit with quality-sorted output
- Human-readable related count in summaries (💬 N sources discussing)
"""
import logging
import re
from datetime import datetime
from math import log10
from typing import Dict, List, Optional, Set
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

TECHMEME_FEED = "https://www.techmeme.com/feed.xml"

# Keyword → category mapping (checked against lowered title + summary)
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "ai": ["artificial intelligence", " ai ", "machine learning", "llm",
            "gpt", "chatgpt", "openai", "anthropic", "gemini", "claude",
            "deep learning", "neural net", "transformer", "diffusion model",
            "generative ai", "gen ai", "copilot", "large language"],
    "security": ["hack", "breach", "vulnerability", "ransomware", "malware",
                  "cyberattack", "phishing", "zero-day", "cve-", "exploit",
                  "encryption", "cybersecurity", "infosec", "data leak",
                  "ddos", "spyware", "backdoor"],
    "crypto": ["bitcoin", "crypto", "blockchain", "ethereum", "web3",
               "nft", "defi", "token", "solana", "stablecoin"],
    "science": ["research", "study finds", "scientists", "nasa", "space",
                "climate", "quantum", "physics", "biology", "genome",
                "crispr", "telescope", "mars", "asteroid", "laboratory"],
    "health": ["health", "medical", "fda", "drug", "vaccine", "hospital",
               "patient", "clinical trial", "disease", "pandemic",
               "mental health", "biotech", "pharma"],
    "business": ["acquisition", "ipo", "valuation", "funding", "layoff",
                 "revenue", "earnings", "merger", "antitrust", "ftc",
                 "sec ", "stock", "investor", "startup raises", "venture",
                 "series a", "series b", "billion"],
    "world": ["ukraine", "china", "eu ", "european union", "nato",
              "sanctions", "geopolit", "diplomat", "united nations",
              "tariff", "trade war", "election"],
    "design": ["design", "figma", "ux ", "ui ", "user experience",
               "typography", "accessibility", "a11y"],
    "gaming": ["gaming", "game", "playstation", "xbox", "nintendo",
               "steam", "esports", "twitch"],
    "culture": ["streaming", "netflix", "spotify", "movie", "film",
                "music", "entertainment", "creator", "tiktok", "youtube"],
    "education": ["education", "university", "college", "student",
                  "academic", "mooc", "coursera", "edtech"],
}

# Known publication domains → display names
_PUBLICATION_DOMAINS: Dict[str, str] = {
    "nytimes.com": "NYT",
    "wsj.com": "WSJ",
    "washingtonpost.com": "WaPo",
    "theverge.com": "The Verge",
    "arstechnica.com": "Ars Technica",
    "techcrunch.com": "TechCrunch",
    "wired.com": "Wired",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "theguardian.com": "The Guardian",
    "bbc.com": "BBC",
    "bbc.co.uk": "BBC",
    "cnbc.com": "CNBC",
    "ft.com": "FT",
    "axios.com": "Axios",
    "theinformation.com": "The Information",
    "semafor.com": "Semafor",
    "404media.co": "404 Media",
    "engadget.com": "Engadget",
    "zdnet.com": "ZDNet",
    "venturebeat.com": "VentureBeat",
    "thenextweb.com": "TNW",
    "9to5mac.com": "9to5Mac",
    "macrumors.com": "MacRumors",
    "protocol.com": "Protocol",
    "platformer.news": "Platformer",
    "stratechery.com": "Stratechery",
}


def _detect_category(title: str, summary: str) -> str:
    """Detect article category from title and summary keywords.
    Prefers specific categories (ai, security, crypto, health) over generic ones.
    """
    text = f"{title} {summary}".lower()
    scores: Dict[str, int] = {}
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score
    if scores:
        # Prefer specific over generic: ai/security/crypto/health get a +0.5 boost
        specific = {"ai", "security", "crypto", "health", "design", "gaming"}
        best_cat = max(scores, key=lambda c: scores[c] + (0.5 if c in specific else 0))
        return best_cat
    return "tech"


def _extract_publication(url: str) -> str:
    """Extract publication name from article URL domain."""
    try:
        # Extract domain from URL
        match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if match:
            domain = match.group(1).lower()
            # Check known publications
            for pub_domain, pub_name in _PUBLICATION_DOMAINS.items():
                if domain.endswith(pub_domain):
                    return pub_name
            # Fallback: capitalize domain parts
            parts = domain.replace(".com", "").replace(".org", "").replace(".net", "").split(".")
            return parts[-1].title()
    except Exception:
        pass
    return ""


def _count_related_links(summary_html: str) -> int:
    """Count related article links in TechMeme RSS summary HTML.
    TechMeme summaries often contain links to other sources discussing the story.
    """
    if not summary_html:
        return 0
    # Count <a href=...> tags in summary (each is a related source)
    links = re.findall(r'<a\s+href=["\']https?://[^"\']+["\']', summary_html, re.IGNORECASE)
    return max(0, len(links) - 1)  # subtract 1 for the main story link


def _compute_quality(related_count: int) -> float:
    """Compute quality score 0–1 based on discussion prominence.
    More sources discussing = higher prominence = higher quality.
    0 related → 0.5 (baseline: TechMeme already curates)
    3 related → ~0.7
    10+ related → ~0.9
    """
    base = 0.5  # TechMeme curation baseline
    if related_count <= 0:
        return base
    # Logarithmic scale: log10(1+count) / log10(15) * 0.45 + base
    bonus = min(0.45, (log10(1 + related_count) / log10(15)) * 0.45)
    return round(min(1.0, base + bonus), 3)


def _fmt_count(n: int) -> str:
    """Human-readable count."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class TechMemeSource(BaseSource):
    """Fetch top tech stories from TechMeme's RSS feed.

    Features:
    - Keyword-based category detection (ai, security, crypto, health, business,
      world, design, gaming, culture, education, science, tech)
    - Source publication extraction from article URL
    - Related articles count from RSS summary HTML
    - Prominence-based quality scoring (more discussion sources = higher)
    - Provenance tags: techmeme:source, techmeme:category, techmeme:topic
    - min_quality, category_filter, global_limit parameters
    """

    name = "techmeme"
    timeout = 15

    def crawl(self) -> List[Article]:
        min_quality = self.config.get("min_quality", 0.0)
        category_filter: Optional[List[str]] = self.config.get("category_filter")
        global_limit: Optional[int] = self.config.get("global_limit")

        text = self.fetch_url(TECHMEME_FEED)
        if not text:
            return []

        feed = feedparser.parse(text)
        articles: List[Article] = []
        seen_urls: Set[str] = set()

        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            if not title or not link:
                continue
            if link in seen_urls:
                continue
            seen_urls.add(link)

            # Get raw summary HTML for related link counting
            raw_summary = getattr(entry, "summary", "") or ""
            related_count = _count_related_links(raw_summary)

            # Clean summary for display
            summary = re.sub(r"<[^>]+>", "", raw_summary).strip()
            if len(summary) > 300:
                summary = summary[:297] + "..."

            timestamp = self._parse_date(entry)
            author = self._extract_author(entry)
            category = _detect_category(title, summary)
            publication = _extract_publication(link)
            quality = _compute_quality(related_count)

            # Apply filters
            if quality < min_quality:
                continue
            if category_filter and category not in category_filter:
                continue

            # TechMeme entry IDs are often the discussion page URL
            discussion_url = ""
            entry_id = getattr(entry, "id", "")
            if entry_id and "techmeme.com" in entry_id and entry_id != link:
                discussion_url = entry_id

            # Build enriched summary
            parts = []
            if publication:
                parts.append(f"📰 {publication}")
            if related_count > 0:
                parts.append(f"💬 {related_count} sources discussing")
            if parts:
                summary = " · ".join(parts) + "\n" + summary if summary else " · ".join(parts)

            # Build tags
            tags = self._extract_topic_tags(title, summary)
            tags.append(f"techmeme:category:{category}")
            if publication:
                tags.append(f"techmeme:source:{publication.lower().replace(' ', '-')}")
            if discussion_url:
                tags.append("techmeme:has-discussion")

            article = Article(
                title=title,
                url=link,
                source="TechMeme",
                summary=summary,
                timestamp=timestamp,
                category=category,
                author=author,
                discussion_url=discussion_url,
                tags=tags,
                quality_score=quality,
            )

            articles.append(article)

        # Sort by quality descending, then apply limit
        articles.sort(key=lambda a: a.quality_score or 0, reverse=True)
        if global_limit and len(articles) > global_limit:
            articles = articles[:global_limit]

        cats = sorted(set(a.category for a in articles))
        logger.info(f"[TechMeme] Parsed {len(articles)} articles across categories: "
                     f"{', '.join(cats)}")
        return articles

    @staticmethod
    def _parse_date(entry) -> Optional[datetime]:
        """Extract and parse date from feed entry."""
        for field in ("published", "updated"):
            raw = getattr(entry, field, None)
            if raw:
                try:
                    return dateparser.parse(raw)
                except (ValueError, OverflowError):
                    pass
        return None

    @staticmethod
    def _extract_author(entry) -> str:
        """Extract author from feed entry metadata."""
        author = getattr(entry, "author", "")
        if not author:
            author_detail = getattr(entry, "author_detail", None)
            if author_detail:
                author = getattr(author_detail, "name", "")
        return author.strip() if author else ""

    @staticmethod
    def _extract_topic_tags(title: str, summary: str) -> List[str]:
        """Extract relevant topic tags from title and summary."""
        text = f"{title} {summary}".lower()
        tags = []
        tag_keywords = {
            "ai": ["artificial intelligence", " ai ", "machine learning", "llm",
                    "gpt", "chatgpt", "openai", "anthropic", "gemini", "claude"],
            "crypto": ["bitcoin", "crypto", "blockchain", "ethereum", "web3"],
            "cloud": ["aws", "azure", "google cloud", "gcp", "cloud computing"],
            "apple": ["apple", "iphone", "ipad", "macos", "wwdc"],
            "google": ["google", "alphabet", "android", "chrome"],
            "meta": ["meta", "facebook", "instagram", "whatsapp", "threads"],
            "microsoft": ["microsoft", "windows", "copilot", "github"],
            "amazon": ["amazon", "aws", "alexa", "kindle"],
            "regulation": ["regulation", "antitrust", "gdpr", "privacy law"],
            "open-source": ["open source", "open-source", "foss", "linux"],
            "semiconductors": ["chip", "semiconductor", "nvidia", "tsmc", "intel", "arm"],
            "robotics": ["robot", "autonomous", "self-driving", "tesla bot"],
            "social-media": ["social media", "tiktok", "twitter", " x ", "bluesky", "threads"],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in text for kw in keywords):
                tags.append(f"techmeme:topic:{tag}")
        return tags
