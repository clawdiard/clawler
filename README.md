# 🗞️ Clawler

**Advanced news crawling service** — no API keys required.

Clawler aggregates news from **250+ individual sources across 44 source types** using RSS feeds, APIs, and web scraping. It deduplicates stories with quality-aware selection and ranks them by a blend of recency and source quality.

## Features

- 📡 **250+ sources across 44 source types** — 54 RSS feeds, Hacker News API, Reddit (21 subreddits), GitHub Trending, Mastodon (4 instances), Lobsters, Wikipedia Current Events, Dev.to, ArXiv, TechMeme, ProductHunt, Bluesky, Tildes, Lemmy (3 instances), Slashdot, Stack Overflow, Pinboard Popular, Indie Hackers, EchoJS, Hashnode (6 topic feeds), freeCodeCamp, Changelog, Hacker Noon, YouTube (22 channels), Medium (20 tags + 10 publications), Google News (5 topics + 8 searches), DZone (12 topic feeds), ScienceDaily (7 section feeds), NPR (10 section feeds), Ars Technica (10 section feeds), AllTop (33 topic categories), Wired (6 section feeds), The Verge, AP News (10 section feeds), The Guardian (10 section feeds), InfoQ (7 topic feeds), The Register (7 section feeds), BBC News (10 section feeds), The Hacker News (cybersecurity)
- 🔑 **No API keys** — works out of the box with public feeds and endpoints
- 🧹 **Smart deduplication** — 3-tier: exact hash, fingerprint, fuzzy title; keeps higher-quality source
- ⚖️ **Quality weighting** — sources scored on credibility, uniqueness, signal-to-noise, freshness, reliability, coverage
- 📊 **Multiple output formats** — Console, JSON, **JSONL**, JSON Feed, Atom, Markdown, CSV, HTML
- 🏷️ **Category filtering** — tech, world, science, business, security, investigative, culture
- ⚡ **Parallel crawling** — concurrent fetching across all sources
- 🩺 **Health tracking** — per-source success rates with automatic score reduction
- 📥 **OPML import/export** — bring your own feed lists
- 📤 **Feed export** — export feed list as YAML (`--export-feeds`)
- 🔍 **Feed discovery** — auto-detect feeds on any URL
- 🎯 **Interest profiles** — relevance scoring based on personal interests
- 📦 **Result caching** — skip network if results are fresh
- 🔥 **Cross-source tracking** — see how many sources covered the same story
- 📂 **Group-by output** — group results by category or source
- 🔄 **Reverse sort** — flip any sort order
- 🩺 **Source health report** — `--source-health` for per-source success rates and article counts
- ⚙️ **Config generator** — `--config-init` creates a starter `~/.clawler.yaml`
- 🔁 **CI pipeline** — GitHub Actions runs tests on Python 3.9–3.12
- 🛡️ **Error resilient** — individual source failures don't break the crawl
- 🚦 **Rate limiting** — per-domain request throttling to be a good citizen
- 📚 **Bookmarks** — save interesting articles locally for later reading
- 📊 **Dedup statistics** — see per-tier dedup breakdown with `--dedupe-stats`
- 🔥 **Trending shorthand** — `--trending` for multi-source stories
- 🔗 **Pipe-friendly output** — `--urls-only` and `--titles-only` for scripting
- 🚫 **Dedup bypass** — `--no-dedup` to see all raw articles
- 🌐 **Domain breakdown** — `--domains` for domain-level analytics
- 🕰️ **Persistent dedup history** — `--history` remembers seen articles across runs (perfect for cron)
- 🌍 **Environment variable config** — `CLAWLER_*` env vars for containerized/CI usage
- 🔇 **Auto-quiet when piped** — suppresses stderr noise when output is piped
- 🎲 **Random sampling** — `--sample N` for serendipitous discovery
- 📦 **Compact JSON** — `--json-compact` for minified single-line JSON
- ⏱️ **Reading time estimation** — `--show-read-time` displays estimated read time; `--min-read`/`--max-read` to filter by duration
- 🎨 **NO_COLOR support** — `--no-color` or `NO_COLOR=1` env var
- 💬 **Discussion URLs** — structured `discussion_url` field on articles (HN, Lobsters, Reddit)
- 📋 **Source list** — `--source-list` shows all configured sources with types and quality weights
- 🔗 **Show discussions** — `--show-discussions` to include discussion links in console output
- 📄 **ArXiv source** — recent CS/AI/ML/physics papers from arXiv's public API (`--no-arxiv` to skip)
- 📰 **TechMeme source** — curated tech news river (`--no-techmeme` to skip)
- 🚀 **ProductHunt source** — trending products (`--no-producthunt` to skip)
- 🦋 **Bluesky source** — trending shared links from the AT Protocol network (`--no-bluesky` to skip)
- 🏛️ **Tildes source** — quality discussion community topics from tildes.net (`--no-tildes` to skip)
- 🐝 **Lemmy source** — trending posts from Fediverse link aggregator instances (`--no-lemmy` to skip)
- 💾 **Slashdot source** — classic tech news and discussion from Slashdot RSS (`--no-slashdot` to skip)
- 🔶 **Stack Overflow source** — hot questions from Stack Overflow's public API (`--no-stackoverflow` to skip)
- 📌 **Pinboard Popular source** — trending community-curated bookmarks from pinboard.in (`--no-pinboard` to skip)
- 🚀 **Indie Hackers source** — trending posts from the bootstrapper/indie maker community (`--no-indiehackers` to skip)
- 📅 **`--since today/this-week/this-month`** — named time periods relative to current calendar boundaries
- 🚫 **`--exclude-domain`** — filter out articles from specific domains (comma-separated)
- ⚡ **Fresh mode** — `--fresh` shorthand for `--since 1h`
- 📅 **ISO date support** — `--since 2026-02-14` or `--since 2026-02-14T10:00:00Z` for absolute time filters
- 🔗 **Smarter URL dedup** — normalizes `www.` prefixes and trailing slashes for better duplicate detection
- 🔐 **The Hacker News source** — cybersecurity news with auto-classification of vulnerabilities, malware, and breaches (`--no-thehackernews` to skip)
- 📰 **AP News source** — trusted wire service, 10 section feeds (`--no-apnews` to skip)
- 🏛️ **The Guardian source** — quality UK/world journalism, 10 section feeds (`--no-guardian` to skip)
- 📓 **Wired source** — premium tech/science/security journalism from 6 section feeds (`--no-wired` to skip)
- 📱 **The Verge source** — major tech publication with auto-categorization (`--no-theverge` to skip)
- 🌐 **Language detection & filtering** — `--lang en,es` to keep specific languages; `--exclude-lang zh` to exclude; lightweight heuristic detection (12 languages, no dependencies)
- 🎨 **`--json-pretty`** — pretty-printed JSON output with 4-space indentation
- ⚙️ **Full config file support** — all 21 source toggles, `lang`, `exclude_lang`, `exclude_domain`, `min_relevance`, `min_quality`, `cache_ttl`, `retries`, `sample` now configurable via `~/.clawler.yaml` or `CLAWLER_*` env vars
- 🔁 **Source-level retry** — failed sources are retried with exponential backoff (`--source-retries N`, `--no-retry`)
- 📅 **Named time periods** — `--since yesterday`, `--since last-week`, `--since last-month`, `--since last-year`
- 📤 **Export health as JSON** — `--export-health FILE` for machine-readable source health data
- 🚫 **Exclude filters** — `--exclude-tag` and `--exclude-author` for precise result trimming
- ⏱️ **Age statistics** — `--age-stats` shows min/max/avg/median article age
- 📡 **Top sources analytics** — `--top-sources` shows which sources contributed the most articles
- 🏷️ **Top tags analytics** — `--top-tags` shows the most common tags across results
- ✍️ **Top authors analytics** — `--top-authors` shows the most prolific authors across results
- 📝 **Top words analytics** — `--top-words` shows the most common words in article titles (stop words excluded)
- ⚖️ **Source quality breakdown** — `--source-quality` shows average quality score per source with article counts
- 🎯 **`--only` source filter** — `--only rss,hn` enables only those sources (cleaner than disabling everything else)
- ⏱️ **Crawl timing** — total crawl time shown on stderr after each run
- 📄 **`--json-lines` alias** — discoverable alias for `-f jsonl`
- 📚 **freeCodeCamp source** — developer tutorials and articles from freeCodeCamp.org (`--no-freecodecamp` to skip)
- 📰 **Digest mode** — `--digest` shorthand for `--since 24h --group-by category --sort quality --format markdown`
- 🎭 **Tone filtering** — `--tone positive/negative/neutral` for sentiment-based filtering
- 🚫 **No-doom mode** — `--no-doom` to exclude strongly negative/doom articles
- 📰 **Changelog source** — developer news and podcasts from changelog.com (`--no-changelog` to skip)
- 📂 **Category stats** — `--category-stats` shows article count per category with percentages
- 🎯 **Profile generator** — `--profile-init` creates a starter interest profile YAML


## Quick Start

```bash
git clone https://github.com/clawdiard/clawler.git
cd clawler
pip install -e .
clawler
```

## Docker

```bash
docker build -t clawler .
docker run --rm clawler                          # default: top 50 stories
docker run --rm clawler --category tech -n 20    # tech news, top 20
docker run --rm clawler -f json | jq '.[0]'      # JSON output
```

## Usage

```bash
# Default: rich console output, top 50 stories
clawler

# JSON output for piping
clawler -f json

# JSON Lines output (one JSON object per line — great for streaming/jq)
clawler -f jsonl

# Pipe JSONL to jq for custom filtering
clawler -f jsonl | jq 'select(.category == "tech")'

# Same thing with --json-lines alias
clawler --json-lines | jq 'select(.category == "tech")'

# Export current feed list as YAML
clawler --export-feeds my-feeds.yaml

# Atom feed output (subscribe in any feed reader)
clawler -f atom -o feed.xml

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

# Articles since a specific date (ISO-8601)
clawler --since 2026-02-14

# Articles since a specific datetime
clawler --since 2026-02-14T10:00:00Z

# Custom retry count
clawler --retries 3

# Search for a topic
clawler -s "climate"

# Verbose logging
clawler -v

# List all sources
clawler --list-sources

# Persistent history — only show NEW articles since last run (great for cron)
clawler --history

# Custom history window (48 hours)
clawler --history --history-ttl 48h

# Check history stats
clawler --history-stats

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

# Only show articles older than 12h (stale content analysis)
clawler --stale 12h

# Show article age distribution
clawler --age-distribution

# Use month/year time units
clawler --since 3M
clawler --max-age 1y

# Control summary truncation length
clawler --summary-length 150

# Output just URLs (great for piping to other tools)
clawler --category tech --urls-only

# Output just titles
clawler --titles-only

# Disable deduplication (see all raw articles)
clawler --no-dedup

# Show domain breakdown after output
clawler --domains

# Generate a starter config file
clawler --config-init

# Show per-source health report
clawler --source-health

# Random sample of 10 articles (serendipity mode)
clawler --sample 10

# Compact JSON (single line, great for streaming/logging)
clawler --json-compact

# Disable colors
clawler --no-color

# Configure via environment variables (great for containers)
CLAWLER_CATEGORY=tech CLAWLER_LIMIT=20 clawler

# Only enable specific sources (cleaner than multiple --no-* flags)
clawler --only rss,hn

# Only Hacker News and Reddit
clawler --only hn,reddit

# Pipe-friendly: stderr is auto-suppressed when piped
clawler -f json | jq '.[] | .title'
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
| TechMeme | RSS | tech | 0.79 |
| ProductHunt | RSS | tech | 0.66 |

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
├── source_weights.yaml # Quality scores for all 65+ sources
├── cache.py            # File-based result caching
├── config.py           # Config file support
├── profile.py          # Interest-based relevance scoring
├── discover.py         # Feed autodiscovery
├── opml.py             # OPML import/export
├── bookmarks.py        # Local bookmark management
├── feeds_config.py     # Custom feed file loading
├── utils.py            # Shared utilities
├── sources/            # 12 source types, 65+ individual sources
│   ├── base.py         # Abstract base source
│   ├── rss.py          # RSS/Atom feed crawler (48 feeds)
│   ├── hackernews.py   # HN Firebase API
│   ├── reddit.py       # Reddit JSON (5 subreddits)
│   ├── github_trending.py # GitHub Trending scraper
│   ├── mastodon.py     # Mastodon trending (4 instances)
│   ├── lobsters.py     # Lobsters hottest
│   ├── wikipedia.py    # Wikipedia Current Events
│   ├── devto.py        # Dev.to top articles
│   ├── arxiv.py        # ArXiv CS/AI/ML papers
│   ├── techmeme.py     # TechMeme curated tech news
│   ├── producthunt.py  # ProductHunt trending
│   ├── bluesky.py      # Bluesky AT Protocol trending
│   └── tildes.py       # Tildes community topics
└── formatters/
    ├── console.py      # Rich terminal output
    ├── json_out.py     # JSON output
    ├── jsonl_out.py    # JSON Lines output (JSONL)
    ├── jsonfeed.py     # JSON Feed format
    ├── atom.py         # Atom 1.0 feed format
    ├── markdown.py     # Markdown output
    ├── csv_out.py      # CSV output
    └── html_out.py     # HTML output
```

## Environment Variables

All CLI flags can be set via `CLAWLER_*` environment variables (CLI flags always win):

| Variable | Example | Equivalent Flag |
|----------|---------|----------------|
| `CLAWLER_CATEGORY` | `tech,science` | `--category tech,science` |
| `CLAWLER_LIMIT` | `25` | `-n 25` |
| `CLAWLER_SINCE` | `6h` | `--since 6h` |
| `CLAWLER_QUIET` | `true` | `--quiet` |
| `CLAWLER_NO_REDDIT` | `1` | `--no-reddit` |
| `CLAWLER_FORMAT` | `json` | `-f json` |
| `CLAWLER_WORKERS` | `4` | `--workers 4` |
| `CLAWLER_DEDUPE_THRESHOLD` | `0.8` | `--dedupe-threshold 0.8` |
| `NO_COLOR` | `1` | `--no-color` |

Priority: CLI flags > environment variables > config files > defaults.

## License

MIT