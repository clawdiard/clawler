"""Data models for Clawler."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, urlencode
import hashlib

# Query parameters known to be tracking/analytics noise (case-insensitive prefix match)
_TRACKING_PREFIXES = (
    "utm_", "fbclid", "gclid", "msclkid", "mc_cid", "mc_eid",
    "oly_enc_id", "oly_anon_id", "_openstat", "vero_id",
    "wickedid", "yclid", "pk_campaign", "pk_kwd", "pk_source",
    "pk_medium", "pk_content", "ref", "referrer", "source",
    "campaign", "icid", "ncid",
)


def _normalize_url(url: str) -> str:
    """Normalize a URL for dedup: strip www., trailing slash, fragment, and tracking query params."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = parsed.path.rstrip("/") or "/"
        # Strip tracking query params, keep meaningful ones
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=False)
            clean = {
                k: v for k, v in params.items()
                if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
            }
            if clean:
                query = urlencode(clean, doseq=True)
                return f"{parsed.scheme}://{host}{path}?{query}"
        return f"{parsed.scheme}://{host}{path}"
    except Exception:
        return url


@dataclass
class Article:
    title: str
    url: str
    source: str
    summary: str = ""
    timestamp: Optional[datetime] = None
    category: str = "general"
    relevance: Optional[float] = None
    quality_score: float = 0.5
    source_count: int = 1  # how many sources covered this story (set during dedup)
    tags: List[str] = field(default_factory=list)  # optional tags/labels (e.g. from HN, Reddit)
    author: str = ""  # article author (when available from source)
    discussion_url: str = ""  # URL to discussion thread (HN, Lobsters, Reddit, etc.)

    @property
    def dedup_key(self) -> str:
        """Generate a deduplication key from normalized title + URL."""
        normalized = self.title.lower().strip()
        norm_url = _normalize_url(self.url)
        return hashlib.md5(f"{normalized}|{norm_url}".encode()).hexdigest()

    @property
    def title_fingerprint(self) -> str:
        """Fuzzy fingerprint based on title words for cross-source dedup.
        Returns empty string if insufficient significant words (avoids false matches)."""
        words = sorted(set(w.lower() for w in self.title.split() if len(w) > 3))
        if len(words) < 2:
            return ""  # Not enough signal for fingerprint dedup
        return hashlib.md5(" ".join(words).encode()).hexdigest()
