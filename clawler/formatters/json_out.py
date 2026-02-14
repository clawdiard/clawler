"""JSON output."""
import json
from typing import List, Optional
from clawler.models import Article


class JSONFormatter:
    def __init__(self, indent: Optional[int] = 2):
        self.indent = indent

    def format(self, articles: List[Article]) -> str:
        return json.dumps([{
            "title": a.title,
            "url": a.url,
            "source": a.source,
            "summary": a.summary,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            "category": a.category,
            "quality_score": round(a.quality_score, 3),
            "source_count": a.source_count,
            "tags": a.tags,
            "author": a.author,
            "discussion_url": a.discussion_url or None,
        } for a in articles], indent=self.indent, ensure_ascii=False)
