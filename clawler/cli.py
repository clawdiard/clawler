"""CLI entry point for Clawler."""
import argparse
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from clawler.engine import CrawlEngine
from clawler.formatters import ConsoleFormatter, CSVFormatter, HTMLFormatter, JSONFormatter, JSONFeedFormatter, MarkdownFormatter

from clawler import __version__


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
    parser.add_argument("-f", "--format", choices=["console", "json", "jsonfeed", "markdown", "csv", "html"], default="console",
                        help="Output format (default: console)")
    parser.add_argument("-n", "--limit", type=int, default=50,
                        help="Max articles to display (default: 50)")
    parser.add_argument("--category", type=str, default="all",
                        help="Filter by category (comma-separated, e.g. tech,science)")
    parser.add_argument("--since", type=str, default=None,
                        help="Only show articles newer than this (e.g. 30m, 2h, 1d, 1w)")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Write output to file instead of stdout")
    parser.add_argument("--source", type=str, default=None,
                        help="Filter articles by source name (substring match, case-insensitive)")
    parser.add_argument("-s", "--search", type=str, default=None,
                        help="Filter articles by keyword in title or summary (case-insensitive)")
    parser.add_argument("--exclude-source", type=str, default=None,
                        help="Exclude articles from sources matching this substring (case-insensitive)")
    parser.add_argument("--exclude-category", type=str, default=None,
                        help="Exclude categories (comma-separated, e.g. business,science)")
    parser.add_argument("--stats", action="store_true",
                        help="Print crawl statistics summary and exit (no articles)")
    parser.add_argument("--sort", choices=["time", "title", "source"], default="time",
                        help="Sort order (default: time)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress status messages on stderr")
    parser.add_argument("--no-reddit", action="store_true", help="Skip Reddit source")
    parser.add_argument("--no-hn", action="store_true", help="Skip Hacker News source")
    parser.add_argument("--no-rss", action="store_true", help="Skip RSS feeds")
    parser.add_argument("--timeout", type=int, default=15,
                        help="HTTP request timeout in seconds (default: 15)")
    parser.add_argument("--check-feeds", action="store_true",
                        help="Test connectivity to all RSS feeds and report status")
    parser.add_argument("--list-sources", action="store_true", help="List all available sources and exit")
    parser.add_argument("--feeds", type=str, default=None,
                        help="Path to custom feeds file (YAML or JSON)")
    parser.add_argument("--export-opml", type=str, default=None, metavar="FILE",
                        help="Export current feed list as OPML and exit")
    parser.add_argument("--import-opml", type=str, default=None, metavar="FILE",
                        help="Import feeds from OPML file (replaces default RSS feeds)")
    parser.add_argument("--dedupe-threshold", type=float, default=0.75, dest="dedupe_threshold",
                        help="Fuzzy title similarity threshold for dedup (0.0-1.0, default: 0.75)")
    parser.add_argument("--discover", type=str, default=None, metavar="URL",
                        help="Discover RSS/Atom feeds on a webpage and exit")
    parser.add_argument("--no-config", action="store_true",
                        help="Ignore config files (~/.clawler.yaml, ./clawler.yaml)")

    args = parser.parse_args()

    # Apply config file defaults (CLI args always win)
    if not args.no_config:
        from clawler.config import apply_config_defaults
        args = apply_config_defaults(parser, args)

    # Feed autodiscovery
    if args.discover:
        from clawler.discover import discover_feeds
        feeds = discover_feeds(args.discover, timeout=args.timeout)
        if feeds:
            print(f"🔍 Found {len(feeds)} feed(s) on {args.discover}:\n")
            for f in feeds:
                print(f"   📡 {f['title']}")
                print(f"      {f['url']}")
                print(f"      Type: {f['type']}\n")
        else:
            print(f"No feeds found on {args.discover}")
        return

    # Determine RSS feeds to use
    custom_feeds = None
    if args.import_opml:
        from clawler.opml import import_opml
        try:
            with open(args.import_opml, "r", encoding="utf-8") as f:
                custom_feeds = import_opml(f.read())
            if not args.quiet:
                print(f"📥 Imported {len(custom_feeds)} feeds from {args.import_opml}", file=sys.stderr)
        except Exception as e:
            print(f"Error importing OPML: {e}", file=sys.stderr)
            sys.exit(1)

    if args.feeds:
        from clawler.feeds_config import load_feeds_file
        try:
            custom_feeds = load_feeds_file(args.feeds)
            if not args.quiet:
                print(f"📂 Loaded {len(custom_feeds)} feeds from {args.feeds}", file=sys.stderr)
        except Exception as e:
            print(f"Error loading feeds file: {e}", file=sys.stderr)
            sys.exit(1)

    if args.export_opml:
        from clawler.opml import export_opml
        from clawler.sources.rss import DEFAULT_FEEDS
        feeds = custom_feeds or DEFAULT_FEEDS
        opml_xml = export_opml(feeds)
        with open(args.export_opml, "w", encoding="utf-8") as f:
            f.write(opml_xml)
        print(f"✅ Exported {len(feeds)} feeds to {args.export_opml}")
        return

    if args.list_sources:
        from clawler.sources.rss import DEFAULT_FEEDS
        feeds = custom_feeds or DEFAULT_FEEDS
        print("📡 RSS Feeds:")
        for f in feeds:
            print(f"   {f.get('source', f['url']):20s} [{f.get('category', 'general')}] — {f['url']}")
        print("\n🔥 Hacker News — https://hacker-news.firebaseio.com/v0/topstories.json")
        print("🤖 Reddit — subreddits: worldnews, technology, science, news, programming")
        return

    if args.check_feeds:
        import requests as _req
        from clawler.sources.rss import DEFAULT_FEEDS
        from clawler.sources.base import HEADERS as _H
        feeds = custom_feeds or DEFAULT_FEEDS
        print(f"🩺 Checking {len(feeds)} feeds (timeout: {args.timeout}s)...\n")
        ok = 0
        for f in feeds:
            try:
                r = _req.get(f["url"], headers=_H, timeout=args.timeout)
                r.raise_for_status()
                print(f"   ✅ {f.get('source', f['url']):20s} [{r.status_code}] {len(r.content)} bytes")
                ok += 1
            except Exception as e:
                print(f"   ❌ {f.get('source', f['url']):20s} {e}")
        print(f"\n📊 {ok}/{len(feeds)} feeds reachable")
        return

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Build source list
    from clawler.sources import RSSSource, HackerNewsSource, RedditSource
    sources = []
    if not args.no_rss:
        src = RSSSource(feeds=custom_feeds) if custom_feeds else RSSSource()
        src.timeout = args.timeout
        sources.append(src)
    if not args.no_hn:
        src = HackerNewsSource()
        src.timeout = args.timeout
        sources.append(src)
    if not args.no_reddit:
        src = RedditSource()
        src.timeout = args.timeout
        sources.append(src)

    if not sources:
        print("Error: All sources disabled!", file=sys.stderr)
        sys.exit(1)

    engine = CrawlEngine(sources=sources)
    if not args.quiet:
        print("🕷️  Crawling news sources...", file=sys.stderr)
    articles, stats = engine.crawl(dedupe_threshold=args.dedupe_threshold)

    # Check if all sources failed
    if all(v == -1 for v in stats.values()):
        print("❌ All sources failed!", file=sys.stderr)
        sys.exit(1)

    # Print source stats
    if not args.quiet:
        for name, count in stats.items():
            status = f"{count} articles" if count >= 0 else "FAILED"
            print(f"   {'✓' if count >= 0 else '✗'} {name}: {status}", file=sys.stderr)

    # Parse multi-category filter
    if args.category != "all":
        cats = set(c.strip().lower() for c in args.category.split(","))
        articles = [a for a in articles if a.category in cats]

    # Filter by source
    if args.source:
        q = args.source.lower()
        articles = [a for a in articles if q in a.source.lower()]

    # Exclude source
    if args.exclude_source:
        eq = args.exclude_source.lower()
        articles = [a for a in articles if eq not in a.source.lower()]

    # Exclude categories
    if args.exclude_category:
        excl_cats = set(c.strip().lower() for c in args.exclude_category.split(","))
        articles = [a for a in articles if a.category not in excl_cats]

    # Filter by keyword search
    if args.search:
        kw = args.search.lower()
        articles = [a for a in articles if kw in a.title.lower() or kw in a.summary.lower()]

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

    # Stats mode
    if args.stats:
        total = sum(v for v in stats.values() if v >= 0)
        failed = sum(1 for v in stats.values() if v == -1)
        print(f"📊 Clawler Crawl Statistics")
        print(f"   Sources crawled: {len(stats)} ({failed} failed)")
        print(f"   Total raw articles: {total}")
        print(f"   After dedup + filters: {len(articles)}")
        cats = {}
        for a in articles:
            cats[a.category] = cats.get(a.category, 0) + 1
        print(f"   Categories: {', '.join(f'{c}={n}' for c, n in sorted(cats.items()))}")
        srcs = {}
        for a in articles:
            srcs[a.source] = srcs.get(a.source, 0) + 1
        top = sorted(srcs.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"   Top sources: {', '.join(f'{s} ({n})' for s, n in top)}")
        return

    # Format
    formatters = {
        "console": ConsoleFormatter, "json": JSONFormatter, "jsonfeed": JSONFeedFormatter,
        "markdown": MarkdownFormatter, "csv": CSVFormatter, "html": HTMLFormatter,
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
