# 🗞️ Clawler

**Advanced news crawling service** — no API keys required.

Clawler aggregates news from multiple sources using web scraping and RSS feeds, deduplicates stories, and presents them in clean, formatted output.

## Features

- 📡 **Multiple sources** — RSS feeds (15+ major outlets), Hacker News, Reddit
- 🔑 **No API keys** — works out of the box with public feeds and endpoints
- 🧹 **Smart deduplication** — exact match + fuzzy title similarity
- 📊 **Multiple output formats** — Rich console, JSON, JSON Feed 1.1, Markdown, CSV, HTML
- 🏷️ **Category filtering** — tech, world, science, business (multi-select + exclude supported)
- ⚡ **Parallel crawling** — concurrent fetching across all sources
- 🛡️ **Error resilient** — individual source failures don't break the crawl
- 📋 **OPML import/export** — interop with other RSS readers
- 📂 **Custom feeds file** — YAML or JSON feed configuration
- 🕐 **Relative timestamps** — "2h ago" in console output
- 🔍 **Feed autodiscovery** — find RSS/Atom feeds on any webpage
- ⚙️ **Config files** — persist defaults in `~/.clawler.yaml`

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

# Multiple categories
clawler --category tech,science

# Only articles from the last 2 hours
clawler --since 2h

# Save markdown digest to file
clawler -f markdown -o digest.md

# CSV export for data analysis
clawler -f csv -o news.csv

# Self-contained HTML digest
clawler -f html -o digest.html

# Filter by source name
clawler --source "BBC"

# Search articles by keyword
clawler --search "AI"

# Sort by title or source instead of time
clawler --sort title

# Exclude a source
clawler --exclude-source "Reddit"

# Exclude categories
clawler --exclude-category business,science

# Show crawl statistics only
clawler --stats

# JSON Feed 1.1 output (for feed readers)
clawler -f jsonfeed -o feed.json

# Quiet mode (no status messages on stderr)
clawler -q -f json

# Skip slow sources
clawler --no-reddit --no-hn

# Verbose logging
clawler -v

# Use custom feeds from a YAML file
clawler --feeds my-feeds.yaml

# Import feeds from OPML
clawler --import-opml subscriptions.opml

# Export current feeds as OPML
clawler --export-opml feeds.opml
```

## Custom Feeds File

Create a YAML or JSON file with your own RSS feeds:

```yaml
# my-feeds.yaml
feeds:
  - url: https://example.com/feed.xml
    source: Example Blog
    category: tech
  - url: https://another.com/rss
    source: Another Site
    category: world
```

```bash
clawler --feeds my-feeds.yaml
```

## OPML Import/Export

Clawler supports OPML for feed portability:

```bash
# Export your feed list for use in other readers
clawler --export-opml my-feeds.opml

# Import feeds from another reader
clawler --import-opml subscriptions.opml

# Discover feeds on a webpage
clawler --discover https://example.com

# Adjust dedup sensitivity (0.0-1.0, default 0.75)
clawler --dedupe-threshold 0.85

# Ignore config files for this run
clawler --no-config
```

## Config File

Create `~/.clawler.yaml` (or `clawler.yaml` in your project) to set defaults:

```yaml
# ~/.clawler.yaml
format: markdown
limit: 25
category: tech,science
since: 6h
quiet: true
no_reddit: true
dedupe_threshold: 0.8
```

CLI arguments always override config file values.

## Sources

| Source | Type | Category |
|--------|------|----------|
| Ars Technica | RSS | tech |
| The Verge | RSS | tech |
| TechCrunch | RSS | tech |
| Wired | RSS | tech |
| The Hacker News | RSS | tech |
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
├── utils.py        # Shared utilities (relative time, etc.)
├── opml.py         # OPML import/export
├── config.py       # Config file loading (~/.clawler.yaml)
├── discover.py     # Feed autodiscovery from webpages
├── feeds_config.py # Custom feeds file loader (YAML/JSON)
├── sources/
│   ├── base.py     # Abstract base source
│   ├── rss.py      # RSS/Atom feed crawler (feedparser)
│   ├── hackernews.py  # HN Firebase API
│   └── reddit.py   # Reddit JSON endpoints
└── formatters/
    ├── console.py  # Rich terminal output (relative timestamps)
    ├── csv_out.py  # CSV output
    ├── html_out.py # Self-contained HTML page
    ├── json_out.py # JSON output
    └── markdown.py # Markdown output
```

## License

MIT
