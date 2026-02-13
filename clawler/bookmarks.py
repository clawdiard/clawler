"""Bookmark management for Clawler.

Save articles to a local bookmarks file for later reading.
Bookmarks are stored as JSON in ~/.clawler/bookmarks.json.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from clawler.models import Article

logger = logging.getLogger(__name__)

DEFAULT_BOOKMARKS_PATH = Path.home() / ".clawler" / "bookmarks.json"


def _article_to_bookmark(article: Article) -> dict:
    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "category": article.category,
        "summary": article.summary,
        "quality_score": article.quality_score,
        "source_count": article.source_count,
        "bookmarked_at": datetime.now(timezone.utc).isoformat(),
    }


def load_bookmarks(path: Path = DEFAULT_BOOKMARKS_PATH) -> List[dict]:
    """Load bookmarks from disk."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"[Bookmarks] Failed to load: {e}")
        return []


def save_bookmarks(bookmarks: List[dict], path: Path = DEFAULT_BOOKMARKS_PATH) -> None:
    """Save bookmarks to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bookmarks, indent=2, ensure_ascii=False), encoding="utf-8")


def add_bookmarks(articles: List[Article], path: Path = DEFAULT_BOOKMARKS_PATH) -> int:
    """Add articles to bookmarks, skipping duplicates by URL. Returns count added."""
    existing = load_bookmarks(path)
    existing_urls = {b["url"] for b in existing}
    added = 0
    for article in articles:
        if article.url not in existing_urls:
            existing.append(_article_to_bookmark(article))
            existing_urls.add(article.url)
            added += 1
    if added:
        save_bookmarks(existing, path)
    return added


def list_bookmarks(path: Path = DEFAULT_BOOKMARKS_PATH, limit: int = 50) -> List[dict]:
    """List bookmarks, most recent first."""
    bookmarks = load_bookmarks(path)
    bookmarks.sort(key=lambda b: b.get("bookmarked_at", ""), reverse=True)
    return bookmarks[:limit]


def remove_bookmark(url: str, path: Path = DEFAULT_BOOKMARKS_PATH) -> bool:
    """Remove a bookmark by URL. Returns True if found and removed."""
    bookmarks = load_bookmarks(path)
    original = len(bookmarks)
    bookmarks = [b for b in bookmarks if b["url"] != url]
    if len(bookmarks) < original:
        save_bookmarks(bookmarks, path)
        return True
    return False


def clear_bookmarks(path: Path = DEFAULT_BOOKMARKS_PATH) -> int:
    """Clear all bookmarks. Returns count removed."""
    bookmarks = load_bookmarks(path)
    count = len(bookmarks)
    if count:
        save_bookmarks([], path)
    return count


def export_bookmarks(bookmarks: List[dict], output_path: str) -> None:
    """Export bookmarks to a file. Format inferred from extension (.json, .md, .csv)."""
    ext = Path(output_path).suffix.lower()
    if ext == ".json":
        Path(output_path).write_text(
            json.dumps(bookmarks, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    elif ext == ".md":
        lines = ["# Clawler Bookmarks\n"]
        for b in bookmarks:
            lines.append(f"- [{b['title']}]({b['url']}) — *{b['source']}* ({b.get('category', 'general')})")
            if b.get("summary"):
                lines.append(f"  > {b['summary'][:200]}")
        Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif ext == ".csv":
        import csv
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "url", "source", "category", "bookmarked_at"])
            writer.writeheader()
            for b in bookmarks:
                writer.writerow({k: b.get(k, "") for k in writer.fieldnames})
    else:
        # Default to JSON
        Path(output_path).write_text(
            json.dumps(bookmarks, indent=2, ensure_ascii=False), encoding="utf-8"
        )
