"""Persistent dedup history for cross-run article tracking.

Stores fingerprints of previously seen articles so that repeated
crawl invocations (e.g. cron-driven) can suppress already-seen
stories.  This is different from the result *cache* (which caches
entire responses to avoid network); history only tracks *what you've
seen* and filters the output.

Usage:
    clawler --history               # enable (default 24h TTL)
    clawler --history --history-ttl 48h   # 48-hour window
    clawler --clear-history         # wipe the history DB

Storage: ~/.cache/clawler/history.json
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import List

from clawler.models import Article

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_DIR = Path.home() / ".cache" / "clawler"
HISTORY_FILE = "history.json"
DEFAULT_HISTORY_TTL = 86400  # 24 hours


def _history_path(history_dir: Path = DEFAULT_HISTORY_DIR) -> Path:
    return history_dir / HISTORY_FILE


def _load_raw(history_dir: Path = DEFAULT_HISTORY_DIR) -> dict:
    """Load raw history data. Returns {fingerprint: timestamp, ...}."""
    path = _history_path(history_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("seen", {})
    except Exception as e:
        logger.warning(f"[History] Failed to load: {e}")
        return {}


def _save_raw(seen: dict, history_dir: Path = DEFAULT_HISTORY_DIR) -> None:
    """Save raw history data."""
    try:
        history_dir.mkdir(parents=True, exist_ok=True)
        path = _history_path(history_dir)
        data = {"seen": seen, "updated_at": time.time()}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[History] Failed to save: {e}")


def _article_fingerprints(article: Article) -> List[str]:
    """Return all fingerprints for an article (dedup_key + title_fingerprint)."""
    fps = [article.dedup_key]
    tf = article.title_fingerprint
    if tf:
        fps.append(tf)
    return fps


def filter_seen(
    articles: List[Article],
    ttl: int = DEFAULT_HISTORY_TTL,
    history_dir: Path = DEFAULT_HISTORY_DIR,
) -> List[Article]:
    """Filter out articles already in history, then record the new ones.

    Returns only articles not previously seen within the TTL window.
    """
    seen = _load_raw(history_dir)
    now = time.time()

    # Prune expired entries
    seen = {fp: ts for fp, ts in seen.items() if now - ts < ttl}

    new_articles = []
    for article in articles:
        fps = _article_fingerprints(article)
        if any(fp in seen for fp in fps):
            continue
        new_articles.append(article)
        # Record all fingerprints
        for fp in fps:
            seen[fp] = now

    _save_raw(seen, history_dir)
    logger.info(
        f"[History] {len(articles)} input → {len(new_articles)} new "
        f"({len(articles) - len(new_articles)} previously seen)"
    )
    return new_articles


def clear_history(history_dir: Path = DEFAULT_HISTORY_DIR) -> bool:
    """Remove the history file. Returns True if a file was removed."""
    path = _history_path(history_dir)
    if path.exists():
        path.unlink()
        return True
    return False


def history_stats(
    ttl: int = DEFAULT_HISTORY_TTL,
    history_dir: Path = DEFAULT_HISTORY_DIR,
) -> dict:
    """Return stats about the current history DB."""
    seen = _load_raw(history_dir)
    now = time.time()
    active = {fp: ts for fp, ts in seen.items() if now - ts < ttl}
    expired = len(seen) - len(active)
    oldest = min(active.values()) if active else None
    return {
        "total_entries": len(seen),
        "active_entries": len(active),
        "expired_entries": expired,
        "oldest_age_hours": round((now - oldest) / 3600, 1) if oldest else None,
    }
