"""Markdown output."""
from typing import List
from clawler.models import Article


class MarkdownFormatter:
    def format(self, articles: List[Article]) -> str:
        lines = [f"# 🗞️ Clawler News Digest — {len(articles)} stories\n"]
        for i, a in enumerate(articles, 1):
            ts = a.timestamp.strftime("%Y-%m-%d %H:%M UTC") if a.timestamp else "unknown"
            lines.append(f"### {i}. {a.title}")
            lines.append(f"**Source:** {a.source} | **Time:** {ts} | **Category:** {a.category}")
            lines.append(f"**URL:** {a.url}")
            if a.summary:
                lines.append(f"> {a.summary[:200]}")
            lines.append("")
        return "\n".join(lines)
