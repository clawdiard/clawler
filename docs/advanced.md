# Advanced Features

## Health Tracking

Clawler tracks per-source reliability in `~/.clawler/health.json`.

### Metrics Tracked
- **total_crawls** — number of crawl attempts
- **failures** — number of failed crawls
- **avg_articles** — average articles per successful crawl
- **last_success** — timestamp of last successful crawl
- **avg_response_ms** — average response time

### Health Modifiers

Poor health automatically reduces effective quality scores:
- Success rate < 80% → 20% score reduction
- Success rate < 50% → 50% score reduction

### Commands

```bash
# View health report
clawler --source-health

# Export health as JSON
clawler --export-health health.json

# Reset health tracking
rm ~/.clawler/health.json
```

## Deduplication

Three-tier deduplication removes duplicate stories:

1. **Exact match** — Hash of normalized title + URL
2. **Fingerprint match** — Sorted significant words (catches cross-source dupes)
3. **Fuzzy match** — SequenceMatcher similarity (default threshold: 0.75)

When duplicates are found, the version from the higher-quality source is kept.

```bash
# Adjust similarity threshold
clawler --dedupe-threshold 0.8

# Disable deduplication
clawler --no-dedup

# View dedup statistics
clawler --dedupe-stats
```

### Cross-Source Tracking

Articles track how many sources covered the same story:

```bash
# Only stories from 2+ sources
clawler --min-sources 2

# Shorthand
clawler --trending
```

## Caching

File-based caching avoids repeated network requests.

```bash
# Set cache TTL (seconds)
clawler --cache-ttl 600

# Disable caching
clawler --no-cache

# Clear cache
rm -rf ~/.cache/clawler/
```

Cache location: `~/.cache/clawler/`

## Retries & Timeouts

```bash
# Retry failed sources
clawler --retries 3
clawler --source-retries 3

# Disable retries
clawler --no-retry

# Per-source timeout (default: 60s)
clawler --source-timeout 30

# Disable source timeout
clawler --no-source-timeout

# Overall request timeout
clawler --timeout 20
```

## Parallel Crawling

Sources are crawled in parallel for speed.

```bash
# Set worker count (default: 6)
clawler --workers 4
```

## Rate Limiting

Per-domain request throttling prevents overwhelming sources.

Built-in delays between requests to the same domain.

## Bookmarks

Save interesting articles for later:

```bash
# Save current results to bookmarks
clawler --category tech --bookmark

# List saved bookmarks
clawler --list-bookmarks

# Remove a bookmark
clawler --remove-bookmark "https://example.com/article"

# Clear all bookmarks
clawler --clear-bookmarks
```

Bookmarks stored in: `~/.clawler/bookmarks.json`

## Watch Mode

Continuously monitor for new articles:

```bash
# Check every 5 minutes
clawler --watch 5m

# Watch with history (only show new)
clawler --watch 10m --history
```

## Digest Mode

Daily digest shorthand:

```bash
clawler --digest
# Equivalent to: --since 24h --group-by category --sort quality --format markdown
```

## Dry Run

See what would be crawled without making requests:

```bash
clawler --dry-run
```

## Debug & Verbose

```bash
# Verbose logging
clawler -v
clawler --verbose

# Quiet mode (suppress non-essential output)
clawler -q
clawler --quiet

# Auto-quiet when piped
clawler -f json | jq '.'  # stderr suppressed automatically
```

## Source Information

```bash
# List all sources
clawler --list-sources

# Detailed source list with types and quality
clawler --source-list

# Check feed health
clawler --check-feeds

# Export source registry as JSON
clawler --export-sources sources.json
```

## Feed Management

```bash
# Export current feeds as YAML
clawler --export-feeds feeds.yaml

# Import OPML
clawler --import-opml reader-export.opml

# Export as OPML
clawler --export-opml feeds.opml

# Discover feeds on a URL
clawler --discover https://example.com
```

## Docker Usage

```bash
# Build
docker build -t clawler .

# Run
docker run --rm clawler
docker run --rm clawler --category tech -n 20
docker run --rm clawler -f json | jq '.[0]'

# With environment variables
docker run --rm -e CLAWLER_CATEGORY=tech -e CLAWLER_LIMIT=20 clawler

# With config file
docker run --rm -v ~/.clawler.yaml:/root/.clawler.yaml clawler
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: News Digest
on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8am

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e .
      - run: clawler --digest -f markdown -o digest.md
      - uses: actions/upload-artifact@v4
        with:
          name: digest
          path: digest.md
```

## Environment Variables Reference

See [Configuration](configuration.md#environment-variables) for the full list.
