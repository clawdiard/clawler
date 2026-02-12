"""CLI entry point for Clawler."""
import argparse
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from clawler.engine import CrawlEngine
from clawler.formatters import ConsoleFormatter, CSVFormatter, HTMLFormatter, JSONFormatter, MarkdownFormatter

__version__ = "1.4.0"


def _parse_since(value: str) -> datetime:
    """Parse a relative time string like '1h', '30m', '2d' into a UTC datetime."""
    match = re.match(r"^(\d+)\s*([mhdw])$", value.strip().lower())
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid --since value '{value}'. Use e.g. 30m, 2h, 1d, 1w"
        )
    amount, unit = int(match.group(1)), match.group(2)
    deltas = {"m": timedelta(minutes=amount), "h": timedelta(hours=amount),
              "d": timedelta(days=amount), "w": timedelta(weeks=amount)}
    return datetime.now(timezone.utc) - deltas[unit]


def main():
    parser = argparse.ArgumentParser(
        prog="clawler",
        description="🗞️ Clawler — Advanced news crawling service",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-f", "--format", choices=["console", "json", "markdown", "csv", "html"], default="console",
                        help="Output format (default: console)")
    parser.add_argument("-n", "--limit", type=int, default=50,
                        help="Max articles to display (default: 50)")
    parser.add_argument("--category", choices=["tech", "world", "science", "business", "all"], default="all",
                        help="Filter by category")
    parser.add_argument("--since", type=str, default=None,
                        help="Only show articles newer than this (e.g. 30m, 2h, 1d, 1w)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Write output to file instead of stdout")
    parser.add_argument("--source", type=str, default=None,
                        help="Filter articles by source name (substring match, case-insensitive)")
    parser.add_argument("--sort", choices=["time", "title", "source"], default="time",
                        help="Sort order (default: time)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress status messages on stderr")
    parser.add_argument("--no-reddit", action="store_true", help="Skip Reddit source")
    parser.add_argument("--no-hn", action="store_true", help="Skip Hacker News source")
    parser.add_argument("--no-rss", action="store_true", help="Skip RSS feeds")
    parser.add_argument("--list-sources", action="store_true", help="List all available sources and exit")

    args = parser.parse_args()

    if args.list_sources:
        from clawler.sources.rss import DEFAULT_FEEDS
        print("📡 RSS Feeds:")
        for f in DEFAULT_FEEDS:
            print(f"   {f['source']:20s} [{f['category']}] — {f['url']}")
        print("\n🔥 Hacker News — https://hacker-news.firebaseio.com/v0/topstories.json")
        print("🤖 Reddit — subreddits: worldnews, technology, science, news, programming")
        return

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Build source list
    from clawler.sources import RSSSource, HackerNewsSource, RedditSource
    sources = []
    if not args.no_rss:
        sources.append(RSSSource())
    if not args.no_hn:
        sources.append(HackerNewsSource())
    if not args.no_reddit:
        sources.append(RedditSource())

    if not sources:
        print("Error: All sources disabled!", file=sys.stderr)
        sys.exit(1)

    engine = CrawlEngine(sources=sources)
    if not args.quiet:
        print("🕷️  Crawling news sources...", file=sys.stderr)
    articles, stats = engine.crawl()

    # Print source stats
    if not args.quiet:
        for name, count in stats.items():
            print(f"   ✓ {name}: {count} articles", file=sys.stderr)

    # Filter by category
    if args.category != "all":
        articles = [a for a in articles if a.category == args.category]

    # Filter by source
    if args.source:
        q = args.source.lower()
        articles = [a for a in articles if q in a.source.lower()]

    # Filter by time
    if args.since:
        cutoff = _parse_since(args.since)
        articles = [a for a in articles if a.timestamp and a.timestamp >= cutoff]

    # Sort
    if args.sort == "title":
        articles.sort(key=lambda a: a.title.lower())
    elif args.sort == "source":
        articles.sort(key=lambda a: a.source.lower())
    # time sort is already applied by the engine

    # Limit
    articles = articles[:args.limit]

    # Format
    formatters = {
        "console": ConsoleFormatter, "json": JSONFormatter, "markdown": MarkdownFormatter,
        "csv": CSVFormatter, "html": HTMLFormatter,
    }
    output = formatters[args.format]().format(articles)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        if not args.quiet:
            print(f"✅ Wrote {len(articles)} articles to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
