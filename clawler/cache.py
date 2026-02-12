"""Simple file-based article cache for Clawler.

Caches crawl results to disk so repeated runs within a TTL window
skip network requests entirely. Useful for scripts that call clawler
multiple times or for reducing load on upstream sources.

Usage:
    clawler --cache              # enable cache (default 5m TTL)
    clawler --cache --cache-ttl 600  # 10 minute TTL

Cache is stored in ~/.cache/clawler/ by default.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from clawler.models import Article

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "clawler"
DEFAULT_TTL = 300  # 5 minutes


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def _article_to_dict(a: Article) -> dict:
    return {
        "title": a.title,
        "url": a.url,
        "source": a.source,
        "summary": a.summary,
        "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        "category": a.category,
        "relevance": a.relevance,
    }


def _dict_to_article(d: dict) -> Article:
    ts = None
    if d.get("timestamp"):
        from dateutil import parser as dateparser
        ts = dateparser.parse(d["timestamp"])
    return Article(
        title=d["title"],
        url=d["url"],
        source=d["source"],
        summary=d.get("summary", ""),
        timestamp=ts,
        category=d.get("category", "general"),
        relevance=d.get("relevance"),
    )


def cache_key(source_names: List[str], dedupe_threshold: float) -> str:
    """Generate a cache key from source config."""
    raw = f"{sorted(source_names)}|{dedupe_threshold}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_cache(
    key: str,
    ttl: int = DEFAULT_TTL,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Optional[Tuple[List[Article], Dict[str, int]]]:
    """Load cached articles if fresh enough. Returns None if stale or missing."""
    path = _cache_path(cache_dir, key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > ttl:
            logger.info(f"[Cache] Stale (age={time.time() - cached_at:.0f}s > ttl={ttl}s)")
            return None
        articles = [_dict_to_article(d) for d in data.get("articles", [])]
        stats = data.get("stats", {})
        logger.info(f"[Cache] Hit: {len(articles)} articles (age={time.time() - cached_at:.0f}s)")
        return articles, stats
    except Exception as e:
        logger.warning(f"[Cache] Failed to load: {e}")
        return None


def save_cache(
    key: str,
    articles: List[Article],
    stats: Dict[str, int],
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> None:
    """Save articles to cache."""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "cached_at": time.time(),
            "stats": stats,
            "articles": [_article_to_dict(a) for a in articles],
        }
        _cache_path(cache_dir, key).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"[Cache] Saved {len(articles)} articles")
    except Exception as e:
        logger.warning(f"[Cache] Failed to save: {e}")


def clear_cache(cache_dir: Path = DEFAULT_CACHE_DIR) -> int:
    """Remove all cache files. Returns count of files removed."""
    if not cache_dir.exists():
        return 0
    count = 0
    for f in cache_dir.glob("*.json"):
        f.unlink()
        count += 1
    return count
