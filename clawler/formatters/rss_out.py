"""RSS 2.0 output formatter — generates a valid RSS 2.0 XML feed."""
import html
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import List
from clawler.models import Article


class RSSFormatter:
    """Format articles as an RSS 2.0 feed."""

    def format(self, articles: List[Article]) -> str:
        now = format_datetime(datetime.now(tz=timezone.utc))
        items = []
        for a in articles:
            title = html.escape(a.title)
            url = html.escape(a.url)
            source = html.escape(a.source)
            summary = html.escape(a.summary[:500]) if a.summary else ""
            category = html.escape(a.category)
            pub_date = ""
            if a.timestamp:
                ts = a.timestamp if a.timestamp.tzinfo else a.timestamp.replace(tzinfo=timezone.utc)
                pub_date = f"<pubDate>{format_datetime(ts)}</pubDate>"
            items.append(
                f"    <item>\n"
                f"      <title>{title}</title>\n"
                f"      <link>{url}</link>\n"
                f"      <description>{summary}</description>\n"
                f"      <source>{source}</source>\n"
                f"      <category>{category}</category>\n"
                f"      <guid isPermaLink=\"true\">{url}</guid>\n"
                f"      {pub_date}\n"
                f"    </item>"
            )
        body = "\n".join(items)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0">\n'
            '  <channel>\n'
            '    <title>Clawler News Digest</title>\n'
            '    <link>https://github.com/clawdiard/clawler</link>\n'
            '    <description>News aggregated by Clawler</description>\n'
            f'    <lastBuildDate>{now}</lastBuildDate>\n'
            f'    <generator>Clawler</generator>\n'
            f'{body}\n'
            '  </channel>\n'
            '</rss>'
        )
