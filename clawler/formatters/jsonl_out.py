"""JSON Lines (JSONL) formatter — one JSON object per line, ideal for streaming and piping."""
import json
from typing import List
from clawler.models import Article


class JSONLFormatter:
    """Output articles as newline-delimited JSON (JSON Lines / JSONL)."""

    def format(self, articles: List[Article]) -> str:
        lines = []
        for a in articles:
            obj = {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "summary": a.summary,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "category": a.category,
                "quality_score": round(a.quality_score, 4),
                "source_count": a.source_count,
            }
            if a.tags:
                obj["tags"] = a.tags
            if a.relevance is not None:
                obj["relevance"] = round(a.relevance, 4)
            lines.append(json.dumps(obj, ensure_ascii=False))
        return "\n".join(lines)
