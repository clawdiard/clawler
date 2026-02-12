"""Rich console output with relative timestamps."""
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from clawler.models import Article
from clawler.utils import relative_time


class ConsoleFormatter:
    def format(self, articles: List[Article]) -> str:
        console = Console(record=True, width=120)
        console.print(Panel(f"[bold cyan]🗞️  Clawler News Digest[/] — {len(articles)} stories", expand=False))
        
        for i, a in enumerate(articles, 1):
            if a.timestamp:
                ts_abs = a.timestamp.strftime("%Y-%m-%d %H:%M")
                ts_rel = relative_time(a.timestamp)
                ts = f"{ts_abs} ({ts_rel})"
            else:
                ts = "—"
            console.print(f"\n[bold white]{i}. {a.title}[/]")
            console.print(f"   [dim]📰 {a.source} | 🕐 {ts} | 🏷️  {a.category}[/]")
            console.print(f"   [blue underline]{a.url}[/]")
            if a.summary:
                console.print(f"   [dim italic]{a.summary[:150]}[/]")
        
        return console.export_text()
