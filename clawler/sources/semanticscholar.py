"""Semantic Scholar source — uses the free public API (no key needed).

Discovers trending and recent academic papers across multiple fields via
the Semantic Scholar Academic Graph API (api.semanticscholar.org).

Features:
- Multi-field search: configurable research fields (CS, medicine, physics, etc.)
- Keyword search queries for targeted discovery
- Quality scoring based on citation velocity, influence, and open access
- Two-tier keyword category detection (12 specific categories)
- Filters: min_citations, min_quality, category_filter, open_access_only
- Cross-field URL deduplication
- Rich summaries with venue, citations, influence score
- Provenance tags: semscholar:field, semscholar:venue, semscholar:category, etc.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Semantic Scholar API base
API_BASE = "https://api.semanticscholar.org/graph/v1"

# Fields to request from the API
PAPER_FIELDS = "title,url,abstract,venue,year,citationCount,influentialCitationCount,isOpenAccess,openAccessPdf,authors,fieldsOfStudy,publicationDate,externalIds"

# Default research fields to search (Semantic Scholar field of study taxonomy)
DEFAULT_FIELDS = [
    "Computer Science",
    "Medicine",
    "Physics",
    "Biology",
    "Mathematics",
    "Engineering",
    "Environmental Science",
    "Economics",
]

# Default keyword searches for high-interest topics
DEFAULT_SEARCHES = [
    "large language model",
    "artificial intelligence safety",
    "quantum computing",
    "CRISPR gene editing",
    "climate change mitigation",
    "cybersecurity",
    "robotics",
    "neural network",
]

# ── Category Detection ──────────────────────────────────────────────

_SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "ai": [
        "machine learning", "deep learning", "neural network", "transformer",
        "language model", "LLM", "GPT", "BERT", "diffusion model", "reinforcement learning",
        "computer vision", "natural language processing", "NLP", "generative AI",
        "artificial intelligence", "fine-tuning", "attention mechanism", "embedding",
        "foundation model", "multimodal", "image generation", "speech recognition",
    ],
    "security": [
        "cybersecurity", "vulnerability", "malware", "encryption", "privacy",
        "adversarial attack", "intrusion detection", "authentication", "zero-day",
        "ransomware", "phishing", "threat detection", "access control", "firewall",
    ],
    "crypto": [
        "blockchain", "cryptocurrency", "bitcoin", "ethereum", "smart contract",
        "decentralized finance", "DeFi", "consensus mechanism", "web3", "token",
    ],
    "health": [
        "clinical trial", "drug discovery", "cancer", "pandemic", "vaccine",
        "diagnosis", "therapy", "patient", "medical imaging", "genomics",
        "epidemiology", "surgery", "disease", "treatment", "public health",
        "mental health", "CRISPR", "gene editing", "biomarker", "pharmaceutical",
    ],
    "science": [
        "quantum", "particle physics", "astrophysics", "cosmology", "gravitational",
        "superconductor", "photonics", "materials science", "nanotechnology",
        "chemistry", "catalysis", "spectroscopy", "fusion", "telescope",
    ],
    "business": [
        "supply chain", "market", "economics", "entrepreneurship", "management",
        "finance", "investment", "corporate", "strategy", "revenue",
    ],
    "world": [
        "climate change", "geopolitics", "policy", "governance", "migration",
        "conflict", "international", "humanitarian", "sustainability", "pollution",
    ],
    "culture": [
        "social media", "digital humanities", "linguistics", "education",
        "psychology", "cognitive science", "sociology", "ethics", "bias",
    ],
    "gaming": [
        "game design", "game engine", "procedural generation", "virtual reality",
        "augmented reality", "VR", "AR", "3D rendering", "game AI",
    ],
    "design": [
        "user experience", "UX", "user interface", "UI", "human-computer interaction",
        "HCI", "visualization", "information design", "accessibility",
    ],
    "education": [
        "online learning", "MOOC", "pedagogy", "student", "curriculum",
        "educational technology", "e-learning", "tutoring", "classroom",
    ],
    "environment": [
        "renewable energy", "solar", "wind power", "carbon capture", "biodiversity",
        "deforestation", "ocean", "ecosystem", "wildlife", "conservation",
        "greenhouse gas", "emission", "sustainable", "recycling",
    ],
}

# Field of study → fallback category
_FIELD_CATEGORY_MAP: Dict[str, str] = {
    "Computer Science": "tech",
    "Medicine": "health",
    "Biology": "science",
    "Physics": "science",
    "Mathematics": "science",
    "Chemistry": "science",
    "Engineering": "tech",
    "Environmental Science": "environment",
    "Economics": "business",
    "Political Science": "world",
    "Psychology": "culture",
    "Sociology": "culture",
    "Linguistics": "culture",
    "Art": "culture",
    "History": "culture",
    "Philosophy": "culture",
    "Geography": "world",
    "Materials Science": "science",
    "Business": "business",
    "Education": "education",
    "Agricultural and Food Sciences": "science",
    "Law": "world",
}


def _detect_category(title: str, abstract: str, fields: List[str]) -> str:
    """Detect article category from title, abstract, and fields of study."""
    text = f"{title} {abstract}".lower()

    # Tier 1: specific keyword categories
    best_cat = None
    best_count = 0
    for cat, keywords in _SPECIFIC_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text)
        if count > best_count:
            best_count = count
            best_cat = cat

    if best_cat and best_count >= 2:
        return best_cat

    # Tier 2: field of study fallback
    for f in fields:
        if f in _FIELD_CATEGORY_MAP:
            return _FIELD_CATEGORY_MAP[f]

    # Tier 1 with single match
    if best_cat and best_count >= 1:
        return best_cat

    return "science"


def _human_count(n: int) -> str:
    """Format large numbers: 1500 → '1.5K', 2300000 → '2.3M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _quality_score(citation_count: int, influential_count: int, is_open_access: bool) -> float:
    """Compute quality score (0–1) based on citation metrics.

    Combines:
    - Citation count (60%): log10 scale, 10 citations ≈ 0.5, 100 ≈ 0.75, 1000 ≈ 1.0
    - Influential citation count (30%): log10 scale, higher weight per citation
    - Open access bonus (10%): open papers get full bonus
    """
    # Citation component
    if citation_count > 0:
        cite_score = min(1.0, math.log10(citation_count + 1) / 3.0)
    else:
        cite_score = 0.0

    # Influential citation component
    if influential_count > 0:
        infl_score = min(1.0, math.log10(influential_count + 1) / 2.0)
    else:
        infl_score = 0.0

    # Open access bonus
    oa_score = 1.0 if is_open_access else 0.0

    return round(cite_score * 0.6 + infl_score * 0.3 + oa_score * 0.1, 4)


class SemanticScholarSource(BaseSource):
    """Crawl trending papers from Semantic Scholar's public API."""

    name = "semanticscholar"

    def crawl(self) -> List[Article]:
        fields = self.config.get("fields", DEFAULT_FIELDS)
        searches = self.config.get("searches", DEFAULT_SEARCHES)
        limit_per_query = self.config.get("limit_per_query", 10)
        global_limit = self.config.get("global_limit", 100)
        min_citations = self.config.get("min_citations", 0)
        min_quality = self.config.get("min_quality", 0.0)
        category_filter = self.config.get("category_filter", None)
        open_access_only = self.config.get("open_access_only", False)
        year_min = self.config.get("year_min", 2024)

        seen_urls: Set[str] = set()
        articles: List[Article] = []

        # 1) Search by keyword queries
        for query in searches:
            self._search_papers(query, limit_per_query, year_min, seen_urls, articles)

        # 2) Search by field of study (recent high-cited papers)
        for fos in fields:
            self._search_by_field(fos, limit_per_query, year_min, seen_urls, articles)

        # Apply filters
        filtered = []
        for a in articles:
            cite_count = 0
            for t in a.tags:
                if t.startswith("semscholar:citations:"):
                    cite_count = int(t.split(":")[-1])
                    break

            if cite_count < min_citations:
                continue
            if a.quality_score < min_quality:
                continue
            if category_filter and a.category not in (category_filter if isinstance(category_filter, list) else [category_filter]):
                continue
            if open_access_only and "semscholar:open-access" not in a.tags:
                continue
            filtered.append(a)

        # Sort by quality, limit
        filtered.sort(key=lambda a: a.quality_score, reverse=True)
        return filtered[:global_limit]

    def _search_papers(self, query: str, limit: int, year_min: int,
                       seen: Set[str], out: List[Article]):
        """Search papers by keyword query."""
        url = (
            f"{API_BASE}/paper/search"
            f"?query={query}"
            f"&limit={limit}"
            f"&fields={PAPER_FIELDS}"
            f"&year={year_min}-"
        )
        data = self.fetch_json(url)
        if not data or "data" not in data:
            return
        for paper in data["data"]:
            self._process_paper(paper, seen, out, provenance_tag=f"semscholar:search:{query.replace(' ', '-')}")

    def _search_by_field(self, field: str, limit: int, year_min: int,
                         seen: Set[str], out: List[Article]):
        """Search recent papers in a field of study, sorted by citation count."""
        url = (
            f"{API_BASE}/paper/search"
            f"?query=*"
            f"&limit={limit}"
            f"&fields={PAPER_FIELDS}"
            f"&year={year_min}-"
            f"&fieldsOfStudy={field}"
        )
        data = self.fetch_json(url)
        if not data or "data" not in data:
            return
        for paper in data["data"]:
            self._process_paper(paper, seen, out, provenance_tag=f"semscholar:field:{field.replace(' ', '-')}")

    def _process_paper(self, paper: dict, seen: Set[str], out: List[Article],
                       provenance_tag: str = ""):
        """Convert a paper dict to Article and add to output."""
        paper_id = paper.get("paperId", "")
        title = paper.get("title", "")
        if not title or not paper_id:
            return

        url = paper.get("url", f"https://www.semanticscholar.org/paper/{paper_id}")
        if url in seen:
            return
        seen.add(url)

        abstract = paper.get("abstract") or ""
        venue = paper.get("venue") or ""
        year = paper.get("year") or ""
        citation_count = paper.get("citationCount") or 0
        influential_count = paper.get("influentialCitationCount") or 0
        is_open_access = paper.get("isOpenAccess") or False
        authors_list = paper.get("authors") or []
        fields_of_study = paper.get("fieldsOfStudy") or []
        pub_date_str = paper.get("publicationDate") or ""
        external_ids = paper.get("externalIds") or {}

        # Parse date
        timestamp = None
        if pub_date_str:
            try:
                timestamp = datetime.strptime(pub_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # Authors
        author_names = [a.get("name", "") for a in authors_list[:5] if a.get("name")]
        author_str = ", ".join(author_names)
        if len(authors_list) > 5:
            author_str += f" +{len(authors_list) - 5} more"

        # Category
        category = _detect_category(title, abstract, fields_of_study)

        # Quality
        quality = _quality_score(citation_count, influential_count, is_open_access)

        # Summary
        parts = []
        if author_str:
            parts.append(f"✍️ {author_str}")
        if venue:
            parts.append(f"📰 {venue}")
        if year:
            parts.append(f"📅 {year}")
        parts.append(f"📊 {_human_count(citation_count)} citations")
        if influential_count > 0:
            parts.append(f"⭐ {_human_count(influential_count)} influential")
        if is_open_access:
            parts.append("🔓 Open Access")
        if abstract:
            trunc = abstract[:280]
            # Truncate at sentence boundary
            last_period = trunc.rfind(".")
            if last_period > 100:
                trunc = trunc[:last_period + 1]
            parts.append(trunc)

        summary = " · ".join(parts[:4])
        if abstract:
            summary += "\n" + parts[-1]

        # Tags
        tags = []
        if provenance_tag:
            tags.append(provenance_tag)
        tags.append(f"semscholar:citations:{citation_count}")
        if influential_count > 0:
            tags.append(f"semscholar:influential:{influential_count}")
        if is_open_access:
            tags.append("semscholar:open-access")
        for fos in fields_of_study:
            tags.append(f"semscholar:field:{fos.replace(' ', '-')}")
        if venue:
            tags.append(f"semscholar:venue:{venue.replace(' ', '-')}")
        tags.append(f"semscholar:category:{category}")
        if external_ids.get("DOI"):
            tags.append(f"semscholar:doi:{external_ids['DOI']}")
        for name in author_names[:3]:
            tags.append(f"semscholar:author:{name.replace(' ', '-')}")
        if len(authors_list) > 1:
            tags.append(f"semscholar:authors:{len(authors_list)}")

        # Open access PDF URL preferred
        oa_pdf = paper.get("openAccessPdf")
        final_url = url
        if oa_pdf and oa_pdf.get("url"):
            final_url = oa_pdf["url"]
            tags.append("semscholar:has-pdf")

        out.append(Article(
            title=title,
            url=final_url,
            source="Semantic Scholar",
            summary=summary,
            timestamp=timestamp,
            category=category,
            quality_score=quality,
            tags=tags,
            author=author_str,
        ))
