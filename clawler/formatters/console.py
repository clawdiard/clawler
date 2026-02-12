"""Rich console output."""
from typing import List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from clawler.models import Article


class ConsoleFormatter:
    def format(self, articles: List[Article]) -> str:
        console = Console(record=True, width=120)
        console.print(Panel(f"[bold cyan]🗞️  Clawler News Digest[/] — {len(articles)} stories", expand=False))
        
        for i, a in enumerate(articles, 1):
            ts = a.timestamp.strftime("%Y-%m-%d %H:%M") if a.timestamp else "—"
            console.print(f"\n[bold white]{i}. {a.title}[/]")
            console.print(f"   [dim]📰 {a.source} | 🕐 {ts} | 🏷️  {a.category}[/]")
            console.print(f"   [blue underline]{a.url}[/]")
            if a.summary:
                console.print(f"   [dim italic]{a.summary[:150]}[/]")
        
        return console.export_text()
