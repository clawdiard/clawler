# Sources

Clawler aggregates content from **75+ source types** spanning news, tech, science, podcasts, and more.

## Source Categories

### News Wire Services
| Source | Sections | Quality | Flag |
|--------|----------|---------|------|
| Reuters | World, Business, Tech, Politics, Environment, Health, Sports, Lifestyle | 0.87-0.91 | `--no-reuters` |
| AP News | Top, World, US, Politics, Business, Tech, Science, Health, Sports, Entertainment | 0.82-0.95 | `--no-apnews` |

### Major Publications
| Source | Sections | Quality | Flag |
|--------|----------|---------|------|
| NY Times | Main feed | 0.84 | `--no-nytimes` |
| Washington Post | Main feed | 0.82 | `--no-washingtonpost` |
| Wall Street Journal | Main feed | 0.83 | `--no-wsj` |
| The Guardian | World, UK, US, Tech, Science, Business, Environment, Culture, Opinion, Sport | 0.80-0.90 | `--no-guardian` |
| The Atlantic | Latest, Best Of, Politics, Tech, Ideas, Science, Health, Culture, Business, International, Family, Education | 0.78-0.88 | `--no-theatlantic` |
| The Economist | World This Week, Leaders, Finance, Science, Business, International, Briefing, US, Asia, Europe, Culture | 0.80-0.90 | `--no-economist` |
| BBC News | Top, World, UK, Business, Tech, Science, Health, Entertainment, Sport | 0.85 | `--no-bbc` |

### Tech Publications
| Source | Sections | Quality | Flag |
|--------|----------|---------|------|
| Ars Technica | Main, Science, AI, Security, Tech Policy, Gaming, Gadgets, Cars, Apple | 0.68-0.82 | `--no-arstechnica` |
| Wired | Main, Science, Security, Business, Culture, Gear | 0.74-0.83 | `--no-wired` |
| The Verge | Main feed | 0.80 | `--no-theverge` |
| TechCrunch | Main feed | 0.88 | `--no-techcrunch` |
| Engadget | Main feed | 0.82 | `--no-engadget` |
| MIT Technology Review | Main feed | 0.81 | `--no-rss` |
| CNET | News, Reviews, How-To, Deals | 0.55-0.72 | `--no-cnet` |
| TechRadar | Main, Computing, Mobile, Gaming | 0.67-0.70 | `--no-techradar` |
| VentureBeat | Main, AI, Gaming, Enterprise | 0.70-0.78 | `--no-venturebeat` |
| The Register | Main, Security, DevOps, Science, Software, AI, Bootnotes | 0.74 | `--no-theregister` |
| InfoQ | Main, AI/ML, Architecture, DevOps, Java, JavaScript, Cloud | 0.75 | `--no-infoq` |

### Science & Research
| Source | Sections | Quality | Flag |
|--------|----------|---------|------|
| Nature | Main, Biotech, Machine Intelligence, Climate, Nanotech | 0.90-0.95 | `--no-nature` |
| ArXiv | CS.AI, CS.LG, Physics | 0.82 | `--no-arxiv` |
| Quanta Magazine | Main feed | 0.85 | `--no-quantamagazine` |
| Phys.org | Breaking, Physics, Nanotech, Tech, Space, Earth, Biology, Chemistry | 0.76-0.80 | `--no-physorg` |
| ScienceDaily | Main feed (7 sections) | 0.72 | `--no-sciencedaily` |
| The Conversation | Main feed | 0.77 | `--no-theconversation` |
| Semantic Scholar | AI-curated papers | 0.80 | `--no-semanticscholar` |

### Medical & Health
| Source | Type | Quality | Flag |
|--------|------|---------|------|
| NEJM | Journal | 0.92 | `--no-nejm` |
| The Lancet | Journal | 0.91 | `--no-thelancet` |
| JAMA | Journal | 0.90 | `--no-jama` |
| STAT News | Health/Biotech news | 0.82 | `--no-statnews` |
| MedPage Today | Medical news | 0.78 | `--no-medpagetoday` |

### Business & Finance
| Source | Sections | Quality | Flag |
|--------|----------|---------|------|
| Bloomberg | Main feed | 0.83 | `--no-rss` |
| CNBC | Top, Finance, Tech, Media, Earnings, World | 0.82-0.87 | `--no-cnbc` |
| MarketWatch | Top, Market Pulse, Software, Personal Finance, Breaking | 0.78-0.84 | `--no-marketwatch` |
| Forbes | Innovation, Business, Leadership, Money, AI, Cybersecurity, Healthcare, Digital Assets, Lifestyle, World | 0.60-0.72 | `--no-forbes` |

### Security
| Source | Type | Quality | Flag |
|--------|------|---------|------|
| Krebs on Security | Blog | 0.81 | `--no-rss` |
| Schneier on Security | Blog | 0.80 | `--no-rss` |
| The Hacker News | Cybersecurity news | 0.70 | `--no-thehackernews` |
| EFF Updates | Digital rights | 0.69 | `--no-rss` |

### Developer & Community
| Source | Type | Quality | Flag |
|--------|------|---------|------|
| Hacker News | API (Top, Best, Show, Ask) | 0.75-0.76 | `--no-hn` |
| Lobsters | RSS | 0.70 | `--no-lobsters` |
| Reddit | JSON (21 subreddits) | 0.62 | `--no-reddit` |
| GitHub Trending | Scraper | 0.72 | `--no-github` |
| Stack Overflow | Hot questions | 0.74 | `--no-stackoverflow` |
| Dev.to | Articles | 0.64 | `--no-devto` |
| Hashnode | Featured, JavaScript, Python, Web Dev, DevOps, AI | 0.63-0.65 | `--no-hashnode` |
| freeCodeCamp | Tutorials | 0.68 | `--no-freecodecamp` |
| DZone | 12 topic feeds | 0.58 | `--no-dzone` |
| Hacker Noon | Articles | 0.64 | `--no-hackernoon` |
| Indie Hackers | Community | 0.67 | `--no-indiehackers` |
| EchoJS | JavaScript news | 0.62 | `--no-echojs` |
| Changelog | Developer news | 0.72 | `--no-changelog` |

### Social & Aggregators
| Source | Type | Quality | Flag |
|--------|------|---------|------|
| TechMeme | Curated tech | 0.79 | `--no-techmeme` |
| Product Hunt | Trending products | 0.66 | `--no-producthunt` |
| Bluesky | AT Protocol trending | 0.64 | `--no-bluesky` |
| Mastodon | 4 instances | 0.60-0.70 | `--no-mastodon` |
| Tildes | Community | 0.73 | `--no-tildes` |
| Lemmy | 3 instances | 0.63 | `--no-lemmy` |
| Slashdot | Classic tech | 0.68 | `--no-slashdot` |
| Pinboard Popular | Bookmarks | 0.71 | `--no-pinboard` |
| Flipboard | 14 topics | 0.65 | `--no-flipboard` |
| MetaFilter | Community | 0.70 | `--no-metafilter` |

### Blogs & Newsletters
| Source | Topics | Quality | Flag |
|--------|--------|---------|------|
| Medium | 20 tags + 10 publications | 0.62-0.74 | `--no-medium` |
| Substack | 10 featured newsletters | 0.70-0.80 | `--no-substack` |
| YouTube | 22 channels | 0.60-0.72 | `--no-youtube` |

### Sports & Entertainment
| Source | Type | Quality | Flag |
|--------|------|---------|------|
| Barstool Sports | Sports/culture | 0.55 | `--no-barstoolsports` |
| Bleacher Report | Sports | 0.60 | `--no-bleacherreport` |

### Podcasts
| Source | Platform | Quality | Flag |
|--------|----------|---------|------|
| Apple Podcasts | Apple/iTunes | 0.72 | `--no-apple_podcasts` |
| Spotify Podcasts | Spotify API | 0.70 | `--no-spotify_podcasts` |
| YouTube Podcasts | YouTube RSS | 0.68 | `--no-youtube_podcasts` |
| Podcast RSS | Direct RSS | 0.65 | `--no-podcast_rss` |

See [Podcasts Documentation](podcasts.md) for podcast-specific features.

## Quality Weighting

Sources are scored from 0.0 to 1.0 based on six dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Credibility | 25% | Editorial standards, fact-checking, corrections policy |
| Uniqueness | 20% | Original reporting vs aggregation |
| Signal-to-noise | 20% | Substantive content vs filler/clickbait |
| Freshness | 15% | How quickly stories appear |
| Reliability | 10% | Feed uptime and consistency |
| Coverage | 10% | Breadth of topics covered |

## Enabling/Disabling Sources

```bash
# Disable specific sources
clawler --no-reddit --no-hn

# Enable only specific sources
clawler --only rss,hn,reddit

# Enable podcasts (disabled by default)
clawler --podcasts

# Only podcasts
clawler --only-podcasts
```

## Adding Custom RSS Feeds

Create a YAML file with your feeds:

```yaml
# my-feeds.yaml
feeds:
  - url: https://example.com/feed.xml
    source: "My Blog"
    category: tech
```

Then use it:

```bash
clawler --feeds my-feeds.yaml
```
