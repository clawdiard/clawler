"""CSV output — handy for spreadsheets and data pipelines."""
import csv
import io
from typing import List
from clawler.models import Article


class CSVFormatter:
    def format(self, articles: List[Article]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["title", "url", "source", "author", "summary", "timestamp", "category", "discussion_url"])
        for a in articles:
            writer.writerow([
                a.title,
                a.url,
                a.source,
                a.author,
                a.summary,
                a.timestamp.isoformat() if a.timestamp else "",
                a.category,
                a.discussion_url,
            ])
        return buf.getvalue()
