"""JSON output."""
import json
from typing import List
from clawler.models import Article


class JSONFormatter:
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
        } for a in articles], indent=2)
