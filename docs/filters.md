# Filtering & Sorting

Clawler provides extensive filtering options to find exactly what you need.

## Time Filters

```bash
# Relative time
clawler --since 30m          # last 30 minutes
clawler --since 6h           # last 6 hours
clawler --since 1d           # last day
clawler --since 1w           # last week
clawler --since 3M           # last 3 months
clawler --since 1y           # last year

# Named periods
clawler --since today        # since midnight
clawler --since yesterday    # since yesterday midnight
clawler --since this-week    # since start of week
clawler --since this-month   # since start of month
clawler --since last-week    # previous week
clawler --since last-month   # previous month

# Absolute dates (ISO-8601)
clawler --since 2026-02-14
clawler --since 2026-02-14T10:00:00Z

# Maximum age (exclude old content)
clawler --max-age 6h

# Fresh content shorthand
clawler --fresh              # same as --since 1h

# Stale content (for analysis)
clawler --stale 12h          # only articles older than 12h
```

## Category Filters

```bash
# Single category
clawler --category tech

# Multiple categories
clawler --category tech,science,security

# Exclude categories
clawler --exclude-category business,sports

# Available categories
# tech, science, world, business, security, investigative, culture, health, sports, entertainment
```

## Quality Filters

```bash
# Minimum source quality score
clawler --min-quality 0.75

# Minimum relevance score (requires --profile)
clawler --profile ~/.clawler_profile.yaml --min-relevance 0.5
```

## Source Filters

```bash
# Disable specific sources
clawler --no-reddit --no-hn --no-github

# Enable only specific sources
clawler --only rss,hn

# Only podcasts
clawler --only-podcasts

# Filter by source name (substring match)
clawler --source "Hacker News"

# Exclude by source
clawler --exclude-source reddit
```

## Content Filters

```bash
# Search in titles/summaries
clawler -s "climate change"
clawler --search "machine learning"

# Filter by tag
clawler --tag python

# Exclude tags
clawler --exclude-tag sponsored

# Filter by author
clawler --author "John Gruber"

# Exclude authors
clawler --exclude-author "Bot"
```

## Domain Filters

```bash
# Exclude specific domains
clawler --exclude-domain medium.com,substack.com
```

## Language Filters

```bash
# Keep only specific languages
clawler --lang en           # English only
clawler --lang en,es        # English and Spanish

# Exclude languages
clawler --exclude-lang zh   # Exclude Chinese

# Supported: en, es, fr, de, it, pt, nl, ru, ja, zh, ko, ar
```

## Duration Filters (Podcasts)

```bash
# Minimum episode length
clawler --only-podcasts --min-duration 30m

# Maximum episode length
clawler --only-podcasts --max-duration 2h
```

## Reading Time Filters

```bash
# Show estimated reading time
clawler --show-read-time

# Filter by reading time
clawler --min-read 5        # at least 5 minutes
clawler --max-read 15       # at most 15 minutes
```

## Tone Filters

```bash
# Filter by sentiment
clawler --tone positive
clawler --tone negative
clawler --tone neutral

# Exclude doom/negative content
clawler --no-doom
```

## Cross-Source Filters

```bash
# Only stories covered by multiple sources
clawler --min-sources 2

# Shorthand for trending
clawler --trending
```

## Sorting

```bash
# Sort by time (default)
clawler --sort time

# Sort by quality score
clawler --sort quality

# Sort by relevance (requires --profile)
clawler --sort relevance

# Reverse any sort
clawler --sort time --reverse
```

## Grouping

```bash
# Group by category
clawler --group-by category

# Group by source
clawler --group-by source
```

## Limiting & Sampling

```bash
# Limit results
clawler -n 20
clawler --limit 20

# Random sample
clawler --sample 10
```

## Deduplication

```bash
# Adjust similarity threshold (default: 0.75)
clawler --dedupe-threshold 0.8

# Disable deduplication
clawler --no-dedup

# Show dedup statistics
clawler --dedupe-stats
```

## LLM Strategy Filter

Filter articles using an LLM-powered sourcing strategy:

```bash
# Create a strategy file
cat > strategy.txt << 'EOF'
Focus on articles about:
- AI safety and alignment research
- Novel machine learning architectures
- Open source AI tools and frameworks

Exclude:
- Product announcements without technical depth
- Cryptocurrency/blockchain unless AI-related
- Opinion pieces without data
EOF

# Apply the strategy
clawler --strategy strategy.txt

# Adjust minimum relevance score
clawler --strategy strategy.txt --strategy-min-score 0.5
```

## Combining Filters

Filters can be combined:

```bash
# Tech news from last 6 hours, high quality, no Reddit
clawler --category tech --since 6h --min-quality 0.75 --no-reddit

# Science articles in English, grouped by source
clawler --category science --lang en --group-by source

# Trending tech stories as JSON
clawler --category tech --trending -f json
```
