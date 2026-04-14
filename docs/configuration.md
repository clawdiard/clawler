# Configuration

Clawler can be configured via CLI flags, environment variables, or config files.

**Priority**: CLI flags > Environment variables > Config file > Defaults

## Config File

Generate a starter config:

```bash
clawler --config-init
```

This creates `~/.clawler.yaml`:

```yaml
# Clawler configuration
limit: 50
category: all
format: console
since: null
quiet: false
verbose: false

# Source toggles
no_reddit: false
no_hn: false
no_github: false
no_mastodon: false

# Quality filters
min_quality: 0.0
min_relevance: 0.0

# Caching
cache_ttl: 300

# Retries
retries: 1

# Language
lang: null
exclude_lang: null

# Domains
exclude_domain: null

# Sampling
sample: 0
```

## Environment Variables

All CLI flags can be set via `CLAWLER_*` environment variables:

| Variable | Example | Equivalent Flag |
|----------|---------|-----------------|
| `CLAWLER_CATEGORY` | `tech,science` | `--category tech,science` |
| `CLAWLER_LIMIT` | `25` | `-n 25` |
| `CLAWLER_SINCE` | `6h` | `--since 6h` |
| `CLAWLER_QUIET` | `true` | `--quiet` |
| `CLAWLER_NO_REDDIT` | `1` | `--no-reddit` |
| `CLAWLER_NO_HN` | `1` | `--no-hn` |
| `CLAWLER_FORMAT` | `json` | `-f json` |
| `CLAWLER_WORKERS` | `4` | `--workers 4` |
| `CLAWLER_DEDUPE_THRESHOLD` | `0.8` | `--dedupe-threshold 0.8` |
| `CLAWLER_MIN_QUALITY` | `0.7` | `--min-quality 0.7` |
| `CLAWLER_LANG` | `en,es` | `--lang en,es` |
| `NO_COLOR` | `1` | `--no-color` |

### API Keys (for Podcast Ingest)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude summarization |
| `OPENAI_API_KEY` | Whisper API / GPT fallback |
| `SPOTIFY_CLIENT_ID` | Spotify podcast source |
| `SPOTIFY_CLIENT_SECRET` | Spotify podcast source |

## Interest Profiles

Create personalized relevance scoring based on your interests.

Generate a starter profile:

```bash
clawler --profile-init
```

This creates `~/.clawler_profile.yaml`:

```yaml
# Interest Profile for Clawler
# Keywords are matched against article titles/summaries
# Weights: 1.0 = normal, >1.0 = boost, <1.0 = reduce

interests:
  # Highly interested
  - keyword: "artificial intelligence"
    weight: 1.5
  - keyword: "machine learning"
    weight: 1.4
  - keyword: "neural network"
    weight: 1.3

  # Moderately interested
  - keyword: "startup"
    weight: 1.2
  - keyword: "open source"
    weight: 1.2

  # Less interested
  - keyword: "crypto"
    weight: 0.5
  - keyword: "NFT"
    weight: 0.3

# Source boosts/penalties
sources:
  "Hacker News": 1.2
  "Reddit": 0.8

# Category weights
categories:
  tech: 1.3
  science: 1.2
  business: 0.9
  sports: 0.5
```

Use the profile:

```bash
# Apply interest profile
clawler --profile ~/.clawler_profile.yaml

# Filter by minimum relevance score
clawler --profile ~/.clawler_profile.yaml --min-relevance 0.5
```

## Custom RSS Feeds

Add your own RSS feeds via YAML:

```yaml
# my-feeds.yaml
feeds:
  - url: https://blog.example.com/feed.xml
    source: "Example Blog"
    category: tech

  - url: https://news.ycombinator.com/rss
    source: "HN RSS"
    category: tech

  - url: https://feeds.bbci.co.uk/news/rss.xml
    source: "BBC"
    category: world
```

```bash
clawler --feeds my-feeds.yaml
```

## OPML Import/Export

Import feeds from an OPML file (e.g., from another feed reader):

```bash
clawler --import-opml feeds.opml
```

Export current feeds to OPML:

```bash
clawler --export-opml my-feeds.opml
```

## Feed Discovery

Auto-detect feeds on any URL:

```bash
clawler --discover https://example.com
```

## Persistent History

Track seen articles across runs (great for cron jobs):

```bash
# Enable history (24h default TTL)
clawler --history

# Custom TTL
clawler --history --history-ttl 48h

# Check history stats
clawler --history-stats

# Clear history
clawler --clear-history
```

History is stored in `~/.cache/clawler/history.json`.
