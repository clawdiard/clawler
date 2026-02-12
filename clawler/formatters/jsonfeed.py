"""JSON Feed 1.1 output — https://www.jsonfeed.org/version/1.1/"""
import json
from typing import List
from clawler.models import Article


class JSONFeedFormatter:
    """Format articles as a JSON Feed 1.1 document."""

    def format(self, articles: List[Article], title: str = "Clawler News Digest") -> str:
        items = []
        for a in articles:
            item = {
                "id": a.url,
                "url": a.url,
                "title": a.title,
                "content_text": a.summary if a.summary else None,
                "date_published": a.timestamp.isoformat() if a.timestamp else None,
                "tags": [a.category] if a.category != "general" else [],
                "_clawler": {"source": a.source},
            }
            # Remove None values for cleanliness
            items.append({k: v for k, v in item.items() if v is not None})

        feed = {
            "version": "https://jsonfeed.org/version/1.1",
            "title": title,
            "items": items,
        }
        return json.dumps(feed, indent=2)
