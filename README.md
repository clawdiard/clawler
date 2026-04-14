# Clawler

**Advanced news aggregation CLI** — 75+ sources, no API keys required.

Clawler crawls news from RSS feeds, APIs, and web scraping. It deduplicates stories, ranks by quality and recency, and outputs in 8 formats.

## Features

- **75+ source types** — News wires, tech publications, science journals, medical journals, podcasts, developer communities, social aggregators
- **No API keys** — Works out of the box (optional keys unlock Spotify podcasts, LLM summarization)
- **Smart deduplication** — 3-tier: exact, fingerprint, fuzzy; keeps higher-quality source
- **Quality scoring** — Sources rated on credibility, uniqueness, signal-to-noise
- **Podcast support** — Discover episodes + AI transcription/summarization
- **8 output formats** — Console, JSON, JSONL, Atom, Markdown, CSV, HTML, JSON Feed
- **Extensive filtering** — Category, time, quality, language, tone, reading time
- **Parallel crawling** — Fast concurrent fetching with per-source timeouts

## Quick Start

```bash
git clone https://github.com/yourusername/clawler.git
cd clawler
pip install -e .
clawler
```

## Basic Usage

```bash
# Default: top 50 stories, rich console output
clawler

# Tech news from last 6 hours
clawler --category tech --since 6h

# High-quality sources only
clawler --min-quality 0.75

# JSON output
clawler -f json

# Pipe to jq
clawler -f jsonl | jq 'select(.category == "science")'

# Only specific sources
clawler --only rss,hn

# Trending (multi-source coverage)
clawler --trending

# Daily digest
clawler --digest
```

## Podcasts

```bash
# Discover new episodes
clawler --only-podcasts --since 7d

# Transcribe and summarize
clawler --only-podcasts --ingest --ingest-limit 2

# Use Whisper API (faster)
clawler --only-podcasts --ingest --whisper-api --ingest-limit 1
```

See [Podcast Documentation](docs/podcasts.md) for full details.

## Docker

```bash
docker build -t clawler .
docker run --rm clawler --category tech -n 20
docker run --rm clawler -f json | jq '.[0]'
```

## Documentation

| Document | Description |
|----------|-------------|
| [Sources](docs/sources.md) | All 75+ sources with quality scores |
| [Podcasts](docs/podcasts.md) | Podcast discovery and AI ingest |
| [Configuration](docs/configuration.md) | Config files, env vars, profiles |
| [Filters](docs/filters.md) | Time, category, quality, language filters |
| [Output Formats](docs/output-formats.md) | JSON, Atom, Markdown, CSV, HTML |
| [Advanced](docs/advanced.md) | Health tracking, caching, Docker, CI/CD |

## Source Highlights

### News
Reuters, AP News, BBC, NY Times, The Guardian, The Atlantic, The Economist, NPR

### Tech
Ars Technica, Wired, The Verge, TechCrunch, Hacker News, Lobsters, GitHub Trending

### Science
Nature, ArXiv, Quanta Magazine, Phys.org, ScienceDaily

### Medical
NEJM, The Lancet, JAMA, STAT News, MedPage Today

### Developer
Stack Overflow, Dev.to, Hashnode, freeCodeCamp, Changelog, Hacker Noon

### Podcasts
21 health/science podcasts with AI transcription and summarization

See [full source list](docs/sources.md).

## Output Formats

```bash
clawler                    # Console (default)
clawler -f json            # JSON array
clawler -f jsonl           # JSON Lines (streaming)
clawler -f atom -o feed.xml  # Atom feed
clawler -f markdown        # Markdown
clawler -f csv             # CSV
clawler -f html            # HTML page
clawler --urls-only        # Just URLs (for piping)
```

## Configuration

```bash
# Generate config file
clawler --config-init      # Creates ~/.clawler.yaml

# Generate interest profile
clawler --profile-init     # Creates ~/.clawler_profile.yaml

# Use custom feeds
clawler --feeds my-feeds.yaml

# Environment variables
CLAWLER_CATEGORY=tech CLAWLER_LIMIT=20 clawler
```

See [Configuration Guide](docs/configuration.md).

## Common Workflows

### Morning Digest
```bash
clawler --digest -f markdown -o ~/digest.md
```

### Cron Job (New Articles Only)
```bash
# Only shows articles not seen in previous runs
clawler --history --category tech -n 20
```

### Research Feed
```bash
clawler --only arxiv,nature --category science --since 1w -f json
```

### Podcast Catchup
```bash
clawler --only-podcasts --since 7d --ingest --ingest-limit 3
```

## License

MIT
