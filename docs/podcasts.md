# Podcast Support

Clawler supports podcast episode discovery and AI-powered transcription/summarization.

## Two Modes

### Surface Mode (Discovery)
Discover and list new podcast episodes from configured feeds.

```bash
# Enable podcast sources
clawler --podcasts

# Only show podcast episodes
clawler --only-podcasts

# Filter by time
clawler --only-podcasts --since 7d

# Filter by category
clawler --only-podcasts --category health
```

### Ingest Mode (Transcription + Summarization)
Download, transcribe (via Whisper), and summarize (via LLM) podcast content.

```bash
# Ingest 2 episodes
clawler --only-podcasts --since 7d --ingest --ingest-limit 2

# Use larger Whisper model for better accuracy
clawler --only-podcasts --ingest --whisper-model medium --ingest-limit 1

# Use OpenAI Whisper API (faster, 25MB limit)
clawler --only-podcasts --ingest --whisper-api --ingest-limit 2

# Different summary styles
clawler --only-podcasts --ingest --summary-style detailed
clawler --only-podcasts --ingest --summary-style bullets
```

## Podcast Sources

| Source | Platform | Requirements |
|--------|----------|--------------|
| Apple Podcasts | iTunes API + RSS | None |
| Spotify Podcasts | Spotify Web API | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` |
| YouTube Podcasts | YouTube RSS | None |
| Podcast RSS | Direct RSS feeds | None |

## Configuration

Podcasts are configured in `clawler/podcast_feeds.yaml`:

```yaml
podcasts:
  - name: "Huberman Lab"
    category: "health"
    quality_weight: 0.85
    spotify_id: "79CkJF3UJTHFV8Dse3Oy0P"
    youtube_channel_id: "UC2D2CMWXMOVWx7giW1n3LIg"
    apple_id: "1545953110"
    rss_url: "https://feeds.megaphone.fm/hubermanlab"
    website_url: "https://hubermanlab.com"

  - name: "The Dr. Hyman Show"
    category: "health"
    quality_weight: 0.78
    apple_id: "1382804627"
    website_url: "https://drhyman.com/podcast"
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Podcast display name |
| `category` | No | Category for filtering (default: "health") |
| `quality_weight` | No | Quality score 0.0-1.0 (default: 0.7) |
| `spotify_id` | No | Spotify show ID |
| `apple_id` | No | Apple Podcasts/iTunes ID |
| `youtube_channel_id` | No | YouTube channel ID |
| `youtube_playlist_id` | No | YouTube playlist ID |
| `rss_url` | No | Direct RSS feed URL |
| `website_url` | No | Podcast website |
| `enabled` | No | Set to `false` to disable (default: true) |

## Ingest CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--ingest` | Enable ingest mode | Off |
| `--ingest-limit N` | Max episodes to process | 5 |
| `--whisper-model SIZE` | Model: tiny, base, small, medium, large | base |
| `--whisper-api` | Use OpenAI Whisper API instead of local | Off |
| `--summary-style STYLE` | executive, detailed, bullets | executive |
| `--save-transcripts` | Save full transcripts to disk | Off |
| `--ingest-cache-dir DIR` | Custom cache directory | ~/.clawler/podcast_cache |

## Ingest Management

```bash
# List ingested episodes
clawler --list-ingested

# Clear ingest cache
clawler --clear-ingest-cache
```

## Requirements

### Transcription
- **Local Whisper**: `pip install faster-whisper` (recommended) or `pip install openai-whisper`
- **OpenAI API**: Set `OPENAI_API_KEY` environment variable

### Summarization
- **Anthropic Claude**: Set `ANTHROPIC_API_KEY` (preferred)
- **OpenAI GPT**: Set `OPENAI_API_KEY` (fallback)

## Ingest Output

Ingested episodes include:
- Full transcript (cached for re-use)
- AI-generated summary (executive, detailed, or bullet points)
- Key topics extracted
- Key takeaways
- Notable quotes (verbatim from transcript)
- Mentioned resources (books, websites, papers)

### Example Output

```
## Summary

In this episode, Dr. Andrew Huberman discusses the neuroscience of sleep...

## Key Topics
- Sleep architecture and circadian rhythms
- Light exposure and melatonin
- Caffeine timing strategies

## Key Takeaways
- Get morning sunlight within 30-60 minutes of waking
- Avoid caffeine after 2pm for optimal sleep
- Keep bedroom temperature between 65-68°F

## Notable Quotes
> "Sleep is the foundation upon which all other health behaviors rest."

## Mentioned Resources
- [Why We Sleep](https://www.amazon.com/Why-We-Sleep-Unlocking-Dreams/dp/1501144324) by Matthew Walker
- Huberman Lab Sleep Toolkit (hubermanlab.com)
```

## Configured Podcasts

The default configuration includes 21 health/science podcasts:

| Podcast | Category | Quality |
|---------|----------|---------|
| Huberman Lab | health | 0.85 |
| Ground Truths with Eric Topol | health | 0.82 |
| Found My Fitness | health | 0.80 |
| Science Vs | health | 0.78 |
| The Dr. Hyman Show | health | 0.78 |
| Dr. Gabrielle Lyon Show | health | 0.76 |
| Joe Rogan Experience | health | 0.75 |
| Medlife Crisis | health | 0.75 |
| New Heights (Kelce Brothers) | health | 0.72 |
| The Human Upgrade (Dave Asprey) | health | 0.72 |
| The Boundless Life | health | 0.70 |
| The Ready State | health | 0.70 |
| Sleep Unplugged | health | 0.70 |
| The Bill Simmons Podcast | health | 0.70 |
| Mind Pump | health | 0.68 |
| Longevity with Natalie Niddam | health | 0.68 |
| Siim Land Podcast | health | 0.66 |
| Brian Johnson Podcast | health | 0.65 |
| Culture Apothecary | health | 0.65 |
| Fit Father Project | health | 0.64 |
| The Goop Podcast | health | 0.60 |

## Custom Podcast Feeds

Use `--podcast-feeds` to specify a custom YAML:

```bash
clawler --only-podcasts --podcast-feeds ~/my-podcasts.yaml
```
