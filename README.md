# 🗞️ Clawler

**Advanced news crawling service** — no API keys required.

Clawler aggregates news from multiple sources using web scraping and RSS feeds, deduplicates stories, and presents them in clean, formatted output.

## Features

- 📡 **Multiple sources** — RSS feeds (15+ major outlets), Hacker News, Reddit
- 🔑 **No API keys** — works out of the box with public feeds and endpoints
- 🧹 **Smart deduplication** — exact match + fuzzy title similarity
- 📊 **Multiple output formats** — Rich console, JSON, Markdown
- 🏷️ **Category filtering** — tech, world, science, business
- ⚡ **Parallel crawling** — concurrent fetching across all sources
- 🛡️ **Error resilient** — individual source failures don't break the crawl

## Quick Start

```bash
git clone https://github.com/clawdiard/clawler.git
cd clawler
pip install -e .
clawler
```

## Usage

```bash
# Default: rich console output, top 50 stories
clawler

# JSON output for piping
clawler -f json

# Markdown output
clawler -f markdown

# Tech news only, top 20
clawler --category tech -n 20

# Only articles from the last 2 hours
clawler --since 2h

# Save markdown digest to file
clawler -f markdown -o digest.md

# Skip slow sources
clawler --no-reddit --no-hn

# Verbose logging
clawler -v
```

## Sources

| Source | Type | Category |
|--------|------|----------|
| Ars Technica | RSS | tech |
| The Verge | RSS | tech |
| TechCrunch | RSS | tech |
| Wired | RSS | tech |
| NY Times | RSS | world |
| BBC News | RSS | world |
| The Guardian | RSS | world |
| Reuters | RSS | world |
| CNN | RSS | world |
| ScienceDaily | RSS | science |
| Phys.org | RSS | science |
| Bloomberg | RSS | business |
| CNBC | RSS | business |
| Hacker News | API | tech |
| Reddit | JSON | various |

## Architecture

```
clawler/
├── cli.py          # CLI entry point
├── engine.py       # Crawl orchestrator (parallel execution)
├── models.py       # Article dataclass with dedup keys
├── dedup.py        # Deduplication (exact + fuzzy)
├── sources/
│   ├── base.py     # Abstract base source
│   ├── rss.py      # RSS/Atom feed crawler (feedparser)
│   ├── hackernews.py  # HN Firebase API
│   └── reddit.py   # Reddit JSON endpoints
└── formatters/
    ├── console.py  # Rich terminal output
    ├── json_out.py # JSON output
    └── markdown.py # Markdown output
```

## License

MIT
