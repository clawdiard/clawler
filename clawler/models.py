"""Data models for Clawler."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import hashlib


@dataclass
class Article:
    title: str
    url: str
    source: str
    summary: str = ""
    timestamp: Optional[datetime] = None
    category: str = "general"

    @property
    def dedup_key(self) -> str:
        """Generate a deduplication key from normalized title + URL."""
        normalized = self.title.lower().strip()
        # Use title + domain for dedup (same story from same source)
        return hashlib.md5(f"{normalized}|{self.url}".encode()).hexdigest()

    @property
    def title_fingerprint(self) -> str:
        """Fuzzy fingerprint based on title words for cross-source dedup."""
        words = sorted(set(w.lower() for w in self.title.split() if len(w) > 3))
        return hashlib.md5(" ".join(words).encode()).hexdigest()
