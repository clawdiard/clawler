# 🗞️ Clawler

**Advanced news crawling service** — no API keys required.

Clawler aggregates news from 46+ sources using RSS feeds, APIs, and web scraping. It deduplicates stories with quality-aware selection and ranks them by a blend of recency and source quality.

## Features

- 📡 **46+ sources** — RSS feeds (43 outlets), Hacker News API, Reddit JSON, GitHub Trending
- 🔑 **No API keys** — works out of the box with public feeds and endpoints
- 🧹 **Smart deduplication** — 3-tier: exact hash, fingerprint, fuzzy title; keeps higher-quality source
- ⚖️ **Quality weighting** — sources scored on credibility, uniqueness, signal-to-noise, freshness, reliability, coverage
- 📊 **Multiple output formats** — Console, JSON, JSON Feed, Markdown, CSV, HTML
- 🏷️ **Category filtering** — tech, world, science, business, security, investigative, culture
- ⚡ **Parallel crawling** — concurrent fetching across all sources
- 🩺 **Health tracking** — per-source success rates with automatic score reduction
- 📥 **OPML import/export** — bring your own feed lists
- 🔍 **Feed discovery** — auto-detect feeds on any URL
- 🎯 **Interest profiles** — relevance scoring based on personal interests
- 📦 **Result caching** — skip network if results are fresh
- 🔥 **Cross-source tracking** — see how many sources covered the same story
- 📂 **Group-by output** — group results by category or source
- 🔄 **Reverse sort** — flip any sort order
- 🛡️ **Error resilient** — individual source failures don't break the crawl
- 🚦 **Rate limiting** — per-domain request throttling to be a good citizen
- 📚 **Bookmarks** — save interesting articles locally for later reading
- 📊 **Dedup statistics** — see per-tier dedup breakdown with `--dedupe-stats`
- 🔥 **Trending shorthand** — `--trending` for multi-source stories


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

# Tech news only, top 20
clawler --category tech -n 20

# Only high-quality sources (score >= 0.75)
clawler --min-quality 0.75

# Security news
clawler --category security

# Skip slow sources
clawler --no-reddit --no-hn

# Skip GitHub Trending
clawler --no-github

# Only articles from last 6 hours
clawler --max-age 6h

# Custom retry count
clawler --retries 3

# Search for a topic
clawler -s "climate"

# Verbose logging
clawler -v

# List all sources
clawler --list-sources

# Check feed health
clawler --check-feeds

# Pretty JSON (shorthand for -f json)
clawler --json-pretty

# Dry run — see what sources would be crawled
clawler --dry-run

# Group by category
clawler --group-by category

# Group by source
clawler --group-by source

# Reverse sort order (oldest first)
clawler --reverse

# Only stories covered by 2+ sources (trending)
clawler --min-sources 2

# Same thing, shorthand
clawler --trending

# Save results to bookmarks for later
clawler --category tech --bookmark

# List saved bookmarks
clawler --list-bookmarks

# Clear bookmarks
clawler --clear-bookmarks

# Show deduplication statistics
clawler --dedupe-stats

# Remove a specific bookmark by URL
clawler --remove-bookmark "https://example.com/article"

# Count articles only (for scripting)
clawler --category tech --count
```

## Sources

| Source | Type | Category | Quality |
|--------|------|----------|---------|
| Reuters | RSS | world | 0.90 |
| BBC News | RSS | world | 0.85 |
| NY Times | RSS | world | 0.84 |
| Nature | RSS | science | 0.84 |
| Bloomberg | RSS | business | 0.83 |
| ProPublica | RSS | investigative | 0.82 |
| Krebs on Security | RSS | security | 0.81 |
| MIT Technology Review | RSS | tech | 0.81 |
| Ars Technica | RSS | tech | 0.81 |
| Schneier on Security | RSS | security | 0.80 |
| Rest of World | RSS | tech | 0.80 |
| NPR | RSS | world | 0.80 |
| The Guardian | RSS | world | 0.80 |
| 404 Media | RSS | tech | 0.79 |
| LWN.net | RSS | tech | 0.78 |
| IEEE Spectrum | RSS | tech | 0.78 |
| Al Jazeera | RSS | world | 0.78 |
| DW | RSS | world | 0.78 |
| The Atlantic | RSS | culture | 0.77 |
| The Conversation | RSS | science | 0.77 |
| Hacker News | API | tech | 0.75 |
| HN Show | RSS | tech | 0.75 |
| HN Ask | RSS | tech | 0.75 |
| ArXiv CS.AI | RSS | science | 0.82 |
| ArXiv CS.LG | RSS | science | 0.82 |
| HN Best | RSS | tech | 0.76 |
| IEEE AI | RSS | tech | 0.78 |
| TorrentFreak | RSS | tech | 0.74 |
| Wired | RSS | tech | 0.73 |
| The Intercept | RSS | investigative | 0.72 |
| TechCrunch | RSS | tech | 0.71 |
| New Scientist | RSS | science | 0.71 |
| Nautilus | RSS | science | 0.71 |
| Lobsters | RSS | tech | 0.70 |
| Phoronix | RSS | tech | 0.70 |
| The Hacker News | RSS | tech | 0.70 |
| TechDirt | RSS | tech | 0.69 |
| ScienceDaily | RSS | science | 0.69 |
| Phys.org | RSS | science | 0.69 |
| EFF Updates | RSS | security | 0.69 |
| The Verge | RSS | tech | 0.68 |
| CNBC | RSS | business | 0.65 |
| CNN | RSS | world | 0.64 |
| Reddit | JSON | various | 0.62 |
| The Next Web | RSS | tech | 0.60 |
| Google News | RSS | world | 0.60 |
| Google News (Tech) | RSS | tech | 0.60 |
| GitHub Trending | Scrape | tech | 0.72 |

## Quality Weighting

Articles are ranked by a blended score: **60% recency + 40% source quality**.

- **Recency** = `max(0, 1.0 - age_hours / 48)` — articles older than 48h get 0
- **Quality** = source score from `source_weights.yaml`, derived from 6 dimensions:
  - Credibility (25%) — editorial standards, fact-checking
  - Uniqueness (20%) — original reporting vs aggregation
  - Signal-to-noise (20%) — substantive content vs filler
  - Freshness (15%) — how quickly stories appear
  - Reliability (10%) — feed uptime and consistency
  - Coverage (10%) — breadth of topics

During deduplication, when the same story appears from multiple sources, the version from the higher-quality source is kept.

## Health Tracking

Clawler tracks per-source health in `~/.clawler/health.json`:

- **total_crawls** — number of crawl attempts
- **failures** — number of failed crawls
- **avg_articles** — average articles per successful crawl
- **last_success** — timestamp of last successful crawl

Health modifiers automatically reduce effective quality scores:
- Success rate < 80% → 20% reduction
- Success rate < 50% → 50% reduction

## Architecture

```
clawler/
├── cli.py              # CLI entry point (30+ flags)
├── engine.py           # Crawl orchestrator (parallel + quality scoring)
├── models.py           # Article dataclass (dedup keys, quality_score, relevance)
├── dedup.py            # 3-tier deduplication (quality-aware)
├── weights.py          # Source quality score lookups
├── health.py           # Per-source health tracking
├── source_weights.yaml # Quality scores for all 42+ sources
├── cache.py            # File-based result caching
├── config.py           # Config file support
├── profile.py          # Interest-based relevance scoring
├── discover.py         # Feed autodiscovery
├── opml.py             # OPML import/export
├── bookmarks.py        # Local bookmark management
├── feeds_config.py     # Custom feed file loading
├── utils.py            # Shared utilities
├── sources/
│   ├── base.py         # Abstract base source
│   ├── rss.py          # RSS/Atom feed crawler (39 feeds)
│   ├── hackernews.py   # HN Firebase API
│   ├── reddit.py       # Reddit JSON endpoints
│   └── github_trending.py # GitHub Trending scraper
└── formatters/
    ├── console.py      # Rich terminal output
    ├── json_out.py     # JSON output
    ├── jsonfeed.py     # JSON Feed format
    ├── markdown.py     # Markdown output
    ├── csv_out.py      # CSV output
    └── html_out.py     # HTML output
```

## License

MIT
