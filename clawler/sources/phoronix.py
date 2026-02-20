"""Phoronix source — Linux hardware reviews, benchmarks & open-source news.

Fetches articles from phoronix.com's public RSS feed. No API key required.

Features:
- Section detection from URL path (news, review, benchmark)
- Two-tier keyword category detection (12 specific categories + fallback)
- Quality scoring based on article type + keyword specificity
- Author extraction from RSS dc:creator
- Configurable filters: min_quality, category_filter, global_limit
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

PHORONIX_RSS = "https://www.phoronix.com/rss.php"

# Dublin Core namespace for dc:creator
DC_NS = "http://purl.org/dc/elements/1.1/"

# Section detection from URL path
_SECTION_PATTERN = re.compile(r"phoronix\.com/(\w+)/")

# Section → base quality score (reviews/benchmarks are higher-effort content)
_SECTION_QUALITY: Dict[str, float] = {
    "review": 0.75,
    "benchmark": 0.70,
    "news": 0.50,
    "scan": 0.40,
}

# Two-tier keyword → category mapping (specific first, generic fallback)
_SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "ai": [
        "machine learning", "deep learning", "neural", "llm", "gpt", "transformer",
        "inference", "training", "cuda", "rocm", "tensor", "onnx", "pytorch",
        "tensorflow", "ai accelerat", "npu", "opencl compute",
    ],
    "security": [
        "vulnerability", "cve-", "exploit", "security", "spectre", "meltdown",
        "mitigation", "sidechannel", "encryption", "tls", "openssl", "selinux",
        "apparmor", "firewall", "audit",
    ],
    "crypto": [
        "cryptocurrency", "blockchain", "bitcoin", "ethereum", "mining",
    ],
    "science": [
        "scientific computing", "hpc", "supercomputer", "simulation", "molecular",
        "physics simulation", "quantum computing",
    ],
    "gaming": [
        "gaming", "steam", "proton", "wine", "dxvk", "vulkan game", "mesa gaming",
        "gamedev", "game performance", "fps benchmark", "nvidia geforce",
        "radeon rx", "gamescope", "mangohud",
    ],
    "design": [
        "wayland", "gnome design", "kde plasma", "desktop environment", "compositor",
        "display server", "color management", "hdr display",
    ],
    "business": [
        "market share", "acquisition", "revenue", "enterprise", "licensing",
        "red hat enterprise",
    ],
    "health": [
        "medical", "healthcare", "bioinformatics",
    ],
    "world": [
        "government", "regulation", "policy", "eu ", "legislation",
    ],
    "education": [
        "university", "academic", "education", "student",
    ],
    "environment": [
        "energy efficiency", "power consumption", "thermal", "cooling", "green computing",
        "carbon", "renewable",
    ],
}

# Generic tech keywords (checked second if no specific match)
_GENERIC_TECH_KEYWORDS: List[str] = [
    "linux", "kernel", "driver", "compiler", "gcc", "llvm", "clang", "rust",
    "mesa", "vulkan", "opengl", "gpu", "cpu", "benchmark", "performance",
    "amd", "intel", "nvidia", "arm", "risc-v", "systemd", "filesystem",
    "ext4", "btrfs", "xfs", "zfs", "ssd", "nvme", "pcie", "usb",
    "thunderbolt", "wifi", "bluetooth", "firmware", "bios", "uefi",
    "ubuntu", "fedora", "debian", "arch", "suse", "gentoo", "freebsd",
]

# Section → fallback category (when no keyword match)
_SECTION_CATEGORY: Dict[str, str] = {
    "review": "tech",
    "benchmark": "tech",
    "news": "tech",
    "scan": "tech",
}


def _detect_category(title: str, description: str) -> str:
    """Two-tier keyword category detection: specific categories first, then generic tech."""
    text = f"{title} {description}".lower()

    # Tier 1: specific categories
    best_cat = ""
    best_count = 0
    for cat, keywords in _SPECIFIC_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > best_count:
            best_count = count
            best_cat = cat

    if best_cat and best_count >= 1:
        return best_cat

    # Tier 2: generic tech keywords
    tech_count = sum(1 for kw in _GENERIC_TECH_KEYWORDS if kw in text)
    if tech_count >= 1:
        return "tech"

    return "tech"  # Phoronix is always tech-related


def _detect_section(url: str) -> str:
    """Extract section from URL path (news, review, benchmark, scan)."""
    m = _SECTION_PATTERN.search(url)
    return m.group(1).lower() if m else "news"


def _compute_quality(section: str, category: str) -> float:
    """Quality score based on section type + category specificity."""
    base = _SECTION_QUALITY.get(section, 0.45)

    # Boost for specific (non-generic) categories
    if category != "tech":
        base = min(base + 0.10, 0.95)

    return round(base, 3)


def _parse_timestamp(date_str: str) -> Optional[datetime]:
    """Parse RSS pubDate."""
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def _human_count(n: int) -> str:
    """Format number as human-readable (1.5K, 2.3M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class PhoronixSource(BaseSource):
    """Fetch articles from Phoronix RSS feed.

    Args:
        min_quality: Minimum quality score threshold (0.0–1.0).
        category_filter: Comma-separated categories to include (e.g. "ai,gaming").
        global_limit: Maximum total articles to return.
    """

    name = "phoronix"

    def __init__(
        self,
        *,
        min_quality: float = 0.0,
        category_filter: str = "",
        global_limit: int = 50,
    ):
        self.min_quality = min_quality
        self.category_filter: Set[str] = (
            {c.strip().lower() for c in category_filter.split(",") if c.strip()}
            if category_filter
            else set()
        )
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        try:
            text = self.fetch_url(PHORONIX_RSS)
            if not text:
                return []
        except Exception as e:
            logger.warning(f"[Phoronix] Failed to fetch RSS: {e}")
            return []

        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as e:
            logger.warning(f"[Phoronix] XML parse error: {e}")
            return []

        seen_urls: set = set()
        articles: List[Article] = []

        for item in root.iter("item"):
            try:
                title = (item.findtext("title") or "").strip()
                url = (item.findtext("link") or "").strip()
                if not title or not url:
                    continue

                # Deduplicate
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                description = (item.findtext("description") or "").strip()
                pub_date = item.findtext("pubDate") or ""
                author = (item.findtext(f"{{{DC_NS}}}creator") or "").strip()

                timestamp = _parse_timestamp(pub_date)
                section = _detect_section(url)
                category = _detect_category(title, description)
                quality = _compute_quality(section, category)

                # Apply filters
                if quality < self.min_quality:
                    continue
                if self.category_filter and category not in self.category_filter:
                    continue

                # Build summary
                summary_parts = []
                if author:
                    summary_parts.append(f"✍️ {author}")
                summary_parts.append(f"📰 {section.title()}")
                if description:
                    # Truncate description at ~280 chars on sentence boundary
                    desc = description
                    if len(desc) > 280:
                        cut = desc[:280].rfind(".")
                        if cut > 100:
                            desc = desc[: cut + 1]
                        else:
                            desc = desc[:277] + "..."
                    summary_parts.append(desc)

                summary = " · ".join(summary_parts[:2])
                if len(summary_parts) > 2:
                    summary += f"\n{summary_parts[2]}"

                # Build tags
                tags = [
                    f"phoronix:section:{section}",
                    f"phoronix:category:{category}",
                ]
                if author:
                    tags.append(f"phoronix:author:{author.lower().replace(' ', '-')}")

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=f"Phoronix ({section.title()})",
                        summary=summary,
                        timestamp=timestamp,
                        category=category,
                        quality_score=quality,
                        tags=tags,
                        author=author,
                    )
                )
            except Exception as e:
                logger.debug(f"[Phoronix] Skipping item: {e}")
                continue

        # Sort by quality descending, apply global limit
        articles.sort(key=lambda a: a.quality_score, reverse=True)
        if self.global_limit and len(articles) > self.global_limit:
            articles = articles[: self.global_limit]

        logger.info(f"[Phoronix] Fetched {len(articles)} articles")
        return articles
