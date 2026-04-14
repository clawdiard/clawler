# Output Formats

Clawler supports 8 output formats for different use cases.

## Console (Default)

Rich terminal output with colors and formatting.

```bash
clawler
clawler -f console
```

Output:
```
╭──────────────────────────────────────╮
│ 🗞️  Clawler News Digest — 50 stories │
╰──────────────────────────────────────╯

1. OpenAI Releases GPT-5 with Reasoning Capabilities
   📰 TechCrunch | 🕐 2h ago | 🏷️  tech
   https://techcrunch.com/2026/04/14/openai-gpt-5
   OpenAI announced GPT-5 today, featuring breakthrough reasoning...
```

Options:
```bash
--no-color           # Disable colors
--show-discussions   # Include discussion URLs (HN, Reddit)
--show-read-time     # Show estimated reading time
--summary-length 200 # Truncate summaries
```

## JSON

Full article data as JSON array.

```bash
clawler -f json
clawler -f json -o articles.json
```

```json
[
  {
    "title": "OpenAI Releases GPT-5",
    "url": "https://techcrunch.com/...",
    "source": "TechCrunch",
    "summary": "OpenAI announced...",
    "timestamp": "2026-04-14T12:00:00Z",
    "category": "tech",
    "quality_score": 0.88,
    "source_count": 3,
    "tags": ["ai", "openai"],
    "author": "Sarah Smith",
    "discussion_url": "https://news.ycombinator.com/item?id=..."
  }
]
```

Options:
```bash
--json-pretty    # Pretty-print with indentation
--json-compact   # Minified single line
```

## JSON Lines (JSONL)

One JSON object per line - great for streaming and `jq`.

```bash
clawler -f jsonl
clawler --json-lines

# Pipe to jq
clawler -f jsonl | jq 'select(.category == "tech")'
clawler -f jsonl | jq -r '.url'
```

## JSON Feed

Standard JSON Feed format (jsonfeed.org).

```bash
clawler -f jsonfeed
clawler -f jsonfeed -o feed.json
```

## Atom

Atom 1.0 feed format - subscribe in any feed reader.

```bash
clawler -f atom -o feed.xml
```

## Markdown

Formatted Markdown output.

```bash
clawler -f markdown
clawler -f markdown -o digest.md
```

Output:
```markdown
# Clawler News Digest

## tech

### [OpenAI Releases GPT-5](https://techcrunch.com/...)
**TechCrunch** | 2h ago | Quality: 0.88

OpenAI announced GPT-5 today, featuring breakthrough reasoning...

---
```

## CSV

Spreadsheet-compatible CSV format.

```bash
clawler -f csv
clawler -f csv -o articles.csv
```

Columns: title, url, source, summary, timestamp, category, quality_score, tags

## HTML

Standalone HTML page.

```bash
clawler -f html -o digest.html
```

## Pipe-Friendly Output

For scripting, use minimal output modes:

```bash
# URLs only
clawler --urls-only
clawler --category tech --urls-only | xargs open

# Titles only
clawler --titles-only

# Count only
clawler --category tech --count
```

## Output to File

```bash
# Any format can be written to file
clawler -f json -o articles.json
clawler -f atom -o feed.xml
clawler -f markdown -o digest.md
```

## Analytics Output

```bash
# Domain breakdown
clawler --domains

# Category statistics
clawler --category-stats

# Age statistics
clawler --age-stats

# Top contributing sources
clawler --top-sources

# Most common tags
clawler --top-tags

# Most prolific authors
clawler --top-authors

# Most common title words
clawler --top-words

# Source quality breakdown
clawler --source-quality

# Dedup statistics
clawler --dedupe-stats
```
