"""CLI entry point for Clawler."""
import argparse
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from clawler.engine import CrawlEngine
from clawler.formatters import AtomFormatter, ConsoleFormatter, CSVFormatter, HTMLFormatter, JSONFormatter, JSONFeedFormatter, JSONLFormatter, MarkdownFormatter, RSSFormatter

from clawler import __version__


def _parse_since(value: str) -> datetime:
    """Parse a relative time string like '1h', '30m', '2d' into a UTC datetime."""
    from clawler.utils import parse_since
    try:
        return parse_since(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid --since value '{value}'. Use e.g. 30m, 2h, 1d, 1w"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="clawler",
        description="🗞️ Clawler — Advanced news crawling service",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-f", "--format", choices=["console", "json", "jsonl", "jsonfeed", "atom", "rss", "markdown", "csv", "html"], default="console",
                        help="Output format (default: console)")
    parser.add_argument("-n", "--limit", "--top", type=int, default=50,
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
    parser.add_argument("--sort", choices=["time", "title", "source", "quality"], default="time",
                        help="Sort order (default: time)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress status messages on stderr")
    parser.add_argument("--no-reddit", action="store_true", help="Skip Reddit source")
    parser.add_argument("--no-hn", action="store_true", help="Skip Hacker News source")
    parser.add_argument("--no-rss", action="store_true", help="Skip RSS feeds")
    parser.add_argument("--no-github", action="store_true", help="Skip GitHub Trending source")
    parser.add_argument("--no-mastodon", action="store_true", help="Skip Mastodon Trending source")
    parser.add_argument("--no-wikipedia", action="store_true", help="Skip Wikipedia Current Events source")
    parser.add_argument("--no-lobsters", action="store_true", help="Skip Lobsters source")
    parser.add_argument("--no-devto", action="store_true", help="Skip Dev.to source")
    parser.add_argument("--no-arxiv", action="store_true", help="Skip ArXiv source")
    parser.add_argument("--no-techmeme", action="store_true", help="Skip TechMeme source")
    parser.add_argument("--no-producthunt", action="store_true", help="Skip ProductHunt source")
    parser.add_argument("--fresh", action="store_true",
                        help="Shorthand for --since 1h (show only articles from the last hour)")
    parser.add_argument("--tag", type=str, default=None,
                        help="Filter articles by tag (substring match, case-insensitive)")
    parser.add_argument("--timeout", type=int, default=15,
                        help="HTTP request timeout in seconds (default: 15)")
    parser.add_argument("--retries", type=int, default=2,
                        help="Max retries per request (default: 2)")
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
    parser.add_argument("--profile", type=str, default=None, metavar="FILE",
                        help="Interest profile (YAML/JSON) for relevance scoring and sorting")
    parser.add_argument("--interests", type=str, default=None,
                        help="Comma-separated interest keywords for relevance scoring (e.g. 'AI,skateboarding,rust'). "
                             "Simpler alternative to --profile.")
    parser.add_argument("--min-relevance", type=float, default=0.0, dest="min_relevance",
                        help="Minimum relevance score (0.0-1.0) when using --profile or --interests (default: 0.0)")
    parser.add_argument("--min-quality", type=float, default=0.0, dest="min_quality",
                        help="Minimum source quality score (0.0-1.0, default: 0.0)")
    parser.add_argument("--cache", action="store_true",
                        help="Enable file-based result cache (skip network if fresh)")
    parser.add_argument("--cache-ttl", type=int, default=300, dest="cache_ttl",
                        help="Cache TTL in seconds (default: 300)")
    parser.add_argument("--clear-cache", action="store_true", dest="clear_cache",
                        help="Clear all cached results and exit")
    parser.add_argument("--history", action="store_true",
                        help="Enable persistent dedup history (suppress previously seen articles across runs)")
    parser.add_argument("--history-ttl", type=str, default="24h", dest="history_ttl",
                        help="History TTL — how long to remember seen articles (e.g. 12h, 2d, 1w; default: 24h)")
    parser.add_argument("--clear-history", action="store_true", dest="clear_history",
                        help="Clear persistent dedup history and exit")
    parser.add_argument("--history-stats", action="store_true", dest="history_stats",
                        help="Show persistent dedup history statistics and exit")
    parser.add_argument("--health", action="store_true",
                        help="Show per-source health report and exit")
    parser.add_argument("--json-pretty", action="store_true", dest="json_pretty",
                        help="Pretty-print JSON output (implies -f json)")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Show which sources would be crawled without fetching")
    parser.add_argument("--reverse", action="store_true",
                        help="Reverse the sort order")
    parser.add_argument("--group-by", choices=["category", "source"], default=None, dest="group_by",
                        help="Group output by category or source")
    parser.add_argument("--min-sources", type=int, default=0, dest="min_sources",
                        help="Only show stories covered by at least N sources (cross-source filter)")
    parser.add_argument("--max-age", type=str, default=None, dest="max_age",
                        help="Exclude articles older than this (e.g. 6h, 1d, 2w). Same syntax as --since.")
    parser.add_argument("--watch", type=str, default=None, metavar="INTERVAL",
                        help="Continuously crawl at an interval (e.g. 5m, 1h). Press Ctrl+C to stop.")
    parser.add_argument("--compact", action="store_true",
                        help="One-line-per-article compact output (implies console format)")
    parser.add_argument("--bookmark", action="store_true",
                        help="Save crawled results to local bookmarks (~/.clawler/bookmarks.json)")
    parser.add_argument("--list-bookmarks", action="store_true", dest="list_bookmarks",
                        help="List saved bookmarks and exit")
    parser.add_argument("--clear-bookmarks", action="store_true", dest="clear_bookmarks",
                        help="Clear all saved bookmarks and exit")
    parser.add_argument("--dedupe-stats", action="store_true", dest="dedupe_stats",
                        help="Show deduplication statistics after crawling")
    parser.add_argument("--trending", action="store_true",
                        help="Shorthand for --min-sources 2 (stories covered by multiple sources)")
    parser.add_argument("--today", action="store_true",
                        help="Shorthand for --since 24h (articles from today)")
    parser.add_argument("--this-week", action="store_true", dest="this_week",
                        help="Shorthand for --since 7d (articles from this week)")
    parser.add_argument("--export-bookmarks", type=str, default=None, metavar="FILE",
                        dest="export_bookmarks",
                        help="Export bookmarks to a file (format inferred from extension: .json, .md, .csv)")
    parser.add_argument("--remove-bookmark", type=str, default=None, metavar="URL",
                        dest="remove_bookmark",
                        help="Remove a bookmark by URL and exit")
    parser.add_argument("--count", action="store_true",
                        help="Print only the article count (useful for scripting)")
    parser.add_argument("--stale", type=str, default=None,
                        help="Only show articles OLDER than this (e.g. 6h, 1d). Inverse of --since.")
    parser.add_argument("--age-distribution", action="store_true", dest="age_distribution",
                        help="Show article age distribution histogram after output")
    parser.add_argument("--summary-length", type=int, default=300, dest="summary_length",
                        help="Max characters for article summaries (default: 300)")
    parser.add_argument("--urls-only", action="store_true", dest="urls_only",
                        help="Output only article URLs, one per line (for piping)")
    parser.add_argument("--titles-only", action="store_true", dest="titles_only",
                        help="Output only article titles, one per line")
    parser.add_argument("--no-dedup", action="store_true", dest="no_dedup",
                        help="Disable deduplication (useful for debugging)")
    parser.add_argument("--domains", action="store_true",
                        help="Show domain breakdown statistics after output")
    parser.add_argument("--workers", type=int, default=6,
                        help="Max parallel workers for crawling (default: 6)")
    parser.add_argument("--exclude", type=str, default=None,
                        help="Exclude articles matching keyword in title or summary (case-insensitive)")
    parser.add_argument("--author", type=str, default=None,
                        help="Filter articles by author name (substring match, case-insensitive)")
    parser.add_argument("--highlight", type=str, default=None,
                        help="Highlight keyword in console output (bold, case-insensitive)")
    parser.add_argument("--export-feeds", type=str, default=None, metavar="FILE",
                        dest="export_feeds",
                        help="Export current feed list as YAML and exit")
    parser.add_argument("--config-init", action="store_true", dest="config_init",
                        help="Generate a starter config file (~/.clawler.yaml) and exit")
    parser.add_argument("--source-health", action="store_true", dest="source_health",
                        help="Show per-source health report (success rates, avg articles) and exit")
    parser.add_argument("--sample", type=int, default=0,
                        help="Randomly sample N articles from results (useful for discovery)")
    parser.add_argument("--json-compact", action="store_true", dest="json_compact",
                        help="Minified single-line JSON output (implies -f json)")
    parser.add_argument("--no-color", action="store_true", dest="no_color",
                        help="Disable colored output (also set via NO_COLOR env var)")
    parser.add_argument("--slow-sources", action="store_true", dest="slow_sources",
                        help="Show sources ranked by average response time and exit")
    parser.add_argument("--source-list", action="store_true", dest="source_list",
                        help="List all configured sources with type and quality weight, then exit")
    parser.add_argument("--show-discussions", action="store_true", dest="show_discussions",
                        help="Include discussion URLs in console output when available")
    parser.add_argument("--exclude-tag", type=str, default=None, dest="exclude_tag",
                        help="Exclude articles matching tag (substring match, case-insensitive)")
    parser.add_argument("--exclude-author", type=str, default=None, dest="exclude_author",
                        help="Exclude articles by author name (substring match, case-insensitive)")
    parser.add_argument("--age-stats", action="store_true", dest="age_stats",
                        help="Show article age statistics (min/max/avg/median) after output")
    parser.add_argument("--top-sources", action="store_true", dest="top_sources",
                        help="Show top contributing sources after output (by article count)")
    parser.add_argument("--silent", action="store_true",
                        help="Alias for --quiet (suppress all status messages on stderr)")

    args = parser.parse_args(argv)

    # --silent is an alias for --quiet
    if args.silent:
        args.quiet = True

    # Auto-quiet when stdout is not a TTY (piped output)
    if not sys.stdout.isatty() and not args.verbose:
        args.quiet = True

    # NO_COLOR env var support (https://no-color.org/)
    import os
    if args.no_color or os.environ.get("NO_COLOR"):
        os.environ["NO_COLOR"] = "1"

    # Determine custom feeds early (needed by --dry-run and other early-exit paths)
    custom_feeds = None

    # Apply config file defaults (CLI args always win)
    if not args.no_config:
        from clawler.config import apply_config_defaults
        args = apply_config_defaults(parser, args)

    # Clear cache
    if args.clear_cache:
        from clawler.cache import clear_cache
        n = clear_cache()
        print(f"🧹 Cleared {n} cached file(s)")
        return

    # Clear history
    if args.clear_history:
        from clawler.history import clear_history
        removed = clear_history()
        print("🧹 Cleared dedup history" if removed else "ℹ️  No history to clear")
        return

    # Config init
    if args.config_init:
        from clawler.config import generate_starter_config
        path = generate_starter_config()
        print(f"✅ Generated starter config at {path}")
        print("   Edit it to customize your default settings.")
        return

    # Source health report
    if args.source_health:
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        report = tracker.get_report()
        if not report:
            print("ℹ️  No health data yet. Run a crawl first.")
            return
        print("🩺 Source Health Report:\n")
        print(f"   {'Source':<25} {'Success%':>8} {'Crawls':>7} {'Avg Articles':>13}")
        print(f"   {'─'*25} {'─'*8} {'─'*7} {'─'*13}")
        for entry in report:
            pct = f"{entry['success_rate']:.0%}"
            avg = f"{entry['avg_articles']:.1f}" if entry['avg_articles'] else "N/A"
            print(f"   {entry['source']:<25} {pct:>8} {entry['total_crawls']:>7} {avg:>13}")
        return

    # Source list
    if args.source_list:
        from clawler.weights import get_quality_score
        from clawler.sources import (RSSSource, HackerNewsSource, RedditSource,
                                      GitHubTrendingSource, MastodonSource,
                                      WikipediaCurrentEventsSource, LobstersSource, DevToSource)
        api_sources = [
            ("Hacker News", "api", "hackernews"),
            ("Reddit", "api", "reddit"),
            ("GitHub Trending", "scrape", "github_trending"),
            ("Mastodon Trending", "api", "mastodon"),
            ("Wikipedia Current Events", "scrape", "wikipedia"),
            ("Lobsters", "api", "lobsters"),
            ("Dev.to", "api", "dev.to"),
            ("ArXiv", "api", "arxiv"),
        ]
        rss = RSSSource()
        print("📡 Configured Sources:\n")
        print(f"   {'Source':<30} {'Type':<8} {'Weight':>7}")
        print(f"   {'─'*30} {'─'*8} {'─'*7}")
        for name, stype, key in api_sources:
            w = get_quality_score(name)
            print(f"   {name:<30} {stype:<8} {w:>7.2f}")
        for feed in rss.feeds:
            name = feed.get("source", feed.get("url", ""))
            w = get_quality_score(name)
            print(f"   {name:<30} {'rss':<8} {w:>7.2f}")
        return

    # Slow sources report (by response time)
    if args.slow_sources:
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        timing = tracker.get_timing_report()
        if not timing:
            print("ℹ️  No timing data yet. Run a crawl first.")
            return
        print("🐢 Sources by Average Response Time:\n")
        print(f"   {'Source':<25} {'Avg ms':>8} {'Min ms':>8} {'Max ms':>8} {'Samples':>8}")
        print(f"   {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
        for entry in timing:
            print(f"   {entry['source']:<25} {entry['avg_ms']:>8.0f} {entry['min_ms']:>8.0f} {entry['max_ms']:>8.0f} {entry['samples']:>8}")
        return

    # History stats
    if args.history_stats:
        from clawler.history import history_stats
        from clawler.utils import parse_since_seconds
        ttl = parse_since_seconds(args.history_ttl)
        stats = history_stats(ttl=ttl)
        print(f"📊 Dedup History Stats:")
        print(f"   Active entries: {stats['active_entries']}")
        print(f"   Expired entries: {stats['expired_entries']}")
        print(f"   Total entries: {stats['total_entries']}")
        if stats['oldest_age_hours'] is not None:
            print(f"   Oldest entry: {stats['oldest_age_hours']}h ago")
        return

    # Bookmarks management
    if args.list_bookmarks:
        from clawler.bookmarks import list_bookmarks
        bookmarks = list_bookmarks()
        if not bookmarks:
            print("📚 No bookmarks saved yet.")
        else:
            print(f"📚 {len(bookmarks)} bookmark(s):\n")
            for b in bookmarks:
                print(f"  • [{b['source']}] {b['title']}")
                print(f"    {b['url']}")
                print(f"    Saved: {b.get('bookmarked_at', 'unknown')}\n")
        return

    if args.clear_bookmarks:
        from clawler.bookmarks import clear_bookmarks
        n = clear_bookmarks()
        print(f"🧹 Cleared {n} bookmark(s)")
        return

    if args.remove_bookmark:
        from clawler.bookmarks import remove_bookmark
        if remove_bookmark(args.remove_bookmark):
            print(f"✅ Removed bookmark: {args.remove_bookmark}")
        else:
            print(f"⚠️  Bookmark not found: {args.remove_bookmark}")
        return

    # --trending is shorthand for --min-sources 2
    if args.trending:
        args.min_sources = max(args.min_sources, 2)

    # --today / --this-week shorthands
    if args.today and not args.since:
        args.since = "24h"
    if args.this_week and not args.since:
        args.since = "7d"
    if args.fresh and not args.since:
        args.since = "1h"

    # Export bookmarks
    if args.export_bookmarks:
        from clawler.bookmarks import list_bookmarks, export_bookmarks
        bookmarks = list_bookmarks()
        if not bookmarks:
            print("📚 No bookmarks to export.")
            return
        export_bookmarks(bookmarks, args.export_bookmarks)
        print(f"✅ Exported {len(bookmarks)} bookmark(s) to {args.export_bookmarks}")
        return

    # Health report
    if args.health:
        from clawler.health import HealthTracker
        tracker = HealthTracker()
        summary = tracker.summary
        if not summary:
            print("🩺 No health data recorded yet. Run a crawl first.")
            return
        print("🩺 Source Health Report\n")
        for source, info in sorted(summary.items(), key=lambda x: x[1]["success_rate"]):
            rate = info["success_rate"]
            emoji = "✅" if rate >= 0.9 else "⚠️" if rate >= 0.7 else "❌"
            print(f"  {emoji} {source:25s}  success={rate:.0%}  crawls={info['total_crawls']}  avg_articles={info['avg_articles']}  last={info['last_success'] or 'never'}")
        return

    # Load custom feeds from OPML or feeds file (before --dry-run so it can report correct feed count)
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

    # Dry run (after feeds loading so custom_feeds is populated)
    if args.dry_run:
        from clawler.sources.rss import DEFAULT_FEEDS
        print("🧪 Dry run — sources that would be crawled:\n")
        if not args.no_rss:
            feeds = custom_feeds if custom_feeds else DEFAULT_FEEDS
            print(f"  📡 RSS ({len(feeds)} feeds)")
        if not args.no_hn:
            print("  🔥 Hacker News (top stories)")
        if not args.no_reddit:
            print("  🤖 Reddit (5 subreddits)")
        if not args.no_github:
            print("  🐙 GitHub Trending (daily)")
        if not args.no_mastodon:
            print("  🐘 Mastodon Trending (4 instances)")
        if not args.no_wikipedia:
            print("  📖 Wikipedia Current Events")
        if not args.no_lobsters:
            print("  🦞 Lobsters (hottest stories)")
        if not args.no_devto:
            print("  📝 Dev.to (latest articles)")
        if not args.no_arxiv:
            print("  📄 ArXiv (recent papers)")
        if not args.no_techmeme:
            print("  📰 TechMeme (curated tech news)")
        if not args.no_producthunt:
            print("  🚀 ProductHunt (trending products)")
        print(f"\n  Timeout: {args.timeout}s | Dedup threshold: {args.dedupe_threshold}")
        return

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

    if args.export_opml:
        from clawler.opml import export_opml
        from clawler.sources.rss import DEFAULT_FEEDS
        feeds = custom_feeds or DEFAULT_FEEDS
        opml_xml = export_opml(feeds)
        with open(args.export_opml, "w", encoding="utf-8") as f:
            f.write(opml_xml)
        print(f"✅ Exported {len(feeds)} feeds to {args.export_opml}")
        return

    if args.export_feeds:
        import yaml
        from clawler.sources.rss import DEFAULT_FEEDS
        feeds = custom_feeds or DEFAULT_FEEDS
        with open(args.export_feeds, "w", encoding="utf-8") as f:
            yaml.dump(feeds, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"✅ Exported {len(feeds)} feeds to {args.export_feeds}")
        return

    if args.list_sources:
        from clawler.sources.rss import DEFAULT_FEEDS
        feeds = custom_feeds or DEFAULT_FEEDS
        print("📡 RSS Feeds:")
        for f in feeds:
            print(f"   {f.get('source', f['url']):20s} [{f.get('category', 'general')}] — {f['url']}")
        print("\n🔥 Hacker News — https://hacker-news.firebaseio.com/v0/topstories.json")
        print("🤖 Reddit — subreddits: worldnews, technology, science, news, programming")
        print("🐘 Mastodon — instances: mastodon.social, mastodon.online, fosstodon.org, hachyderm.io")
        print("🦞 Lobsters — https://lobste.rs/hottest.json")
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
    from clawler.sources import RSSSource, HackerNewsSource, RedditSource, GitHubTrendingSource, MastodonSource, LobstersSource
    sources = []
    if not args.no_rss:
        src = RSSSource(feeds=custom_feeds) if custom_feeds else RSSSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_hn:
        src = HackerNewsSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_reddit:
        src = RedditSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_github:
        src = GitHubTrendingSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_mastodon:
        src = MastodonSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_wikipedia:
        from clawler.sources import WikipediaCurrentEventsSource
        src = WikipediaCurrentEventsSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_lobsters:
        src = LobstersSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_devto:
        from clawler.sources import DevToSource
        src = DevToSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_arxiv:
        from clawler.sources import ArXivSource
        src = ArXivSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_techmeme:
        from clawler.sources import TechMemeSource
        src = TechMemeSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)
    if not args.no_producthunt:
        from clawler.sources import ProductHuntSource
        src = ProductHuntSource()
        src.timeout = args.timeout
        src.max_retries = args.retries
        sources.append(src)

    if not sources:
        print("Error: All sources disabled!", file=sys.stderr)
        sys.exit(1)

    engine = CrawlEngine(sources=sources, max_workers=args.workers)
    if not args.quiet:
        print("🕷️  Crawling news sources...", file=sys.stderr)

    # Check cache first
    articles = None
    stats = None
    _dedup_stats = None
    if args.cache:
        from clawler.cache import cache_key, load_cache, save_cache
        ckey = cache_key([s.name for s in sources], args.dedupe_threshold)
        cached = load_cache(ckey, ttl=args.cache_ttl)
        if cached:
            articles, stats = cached
            if not args.quiet:
                print("📦 Using cached results", file=sys.stderr)

    if articles is None:
        articles, stats, _dedup_stats = engine.crawl(
            dedupe_threshold=args.dedupe_threshold,
            dedupe_enabled=not args.no_dedup,
        )
        if args.cache:
            save_cache(ckey, articles, stats)

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

    # Exclude by keyword (inverse of --search)
    if args.exclude:
        ekw = args.exclude.lower()
        articles = [a for a in articles if ekw not in a.title.lower() and ekw not in a.summary.lower()]

    # Filter by author
    if args.author:
        aq = args.author.lower()
        articles = [a for a in articles if aq in a.author.lower()]

    # Filter by tag
    if args.tag:
        tq = args.tag.lower()
        articles = [a for a in articles if any(tq in t.lower() for t in a.tags)]

    # Exclude by tag
    if args.exclude_tag:
        etq = args.exclude_tag.lower()
        articles = [a for a in articles if not any(etq in t.lower() for t in a.tags)]

    # Exclude by author
    if args.exclude_author:
        eaq = args.exclude_author.lower()
        articles = [a for a in articles if eaq not in a.author.lower()]

    # Filter by time (--since)
    if args.since:
        cutoff = _parse_since(args.since)
        articles = [a for a in articles if a.timestamp and a.timestamp >= cutoff]

    # Filter by max age (--max-age) — excludes articles older than threshold
    if args.max_age:
        cutoff = _parse_since(args.max_age)
        articles = [a for a in articles if a.timestamp and a.timestamp >= cutoff]

    # Filter by staleness (--stale) — only articles OLDER than threshold
    if args.stale:
        stale_cutoff = _parse_since(args.stale)
        articles = [a for a in articles if a.timestamp and a.timestamp < stale_cutoff]

    # Filter by quality score
    if args.min_quality > 0:
        articles = [a for a in articles if a.quality_score >= args.min_quality]

    # Filter by cross-source coverage
    if args.min_sources > 0:
        articles = [a for a in articles if a.source_count >= args.min_sources]

    # Sort
    if args.sort == "title":
        articles.sort(key=lambda a: a.title.lower())
    elif args.sort == "source":
        articles.sort(key=lambda a: a.source.lower())
    elif args.sort == "quality":
        articles.sort(key=lambda a: a.quality_score, reverse=True)
    # time sort is already applied by the engine

    # Reverse sort if requested
    if args.reverse:
        articles.reverse()

    # Profile-based relevance scoring (--profile file or --interests string)
    profile_data = None
    if args.profile:
        profile_data = args.profile
    elif args.interests:
        from clawler.profile import interests_to_profile
        profile_data = interests_to_profile(args.interests)

    if profile_data:
        from clawler.profile import score_articles
        articles = score_articles(articles, profile_data, min_relevance=args.min_relevance)

    # Truncate summaries to configured length
    max_summary = args.summary_length
    for a in articles:
        if len(a.summary) > max_summary:
            a.summary = a.summary[:max_summary] + "..."

    # Persistent dedup history — filter out previously seen articles
    if args.history:
        from clawler.history import filter_seen
        from clawler.utils import parse_since_seconds
        history_ttl = parse_since_seconds(args.history_ttl)
        articles = filter_seen(articles, ttl=history_ttl)

    # Limit
    articles = articles[:args.limit]

    # Random sampling (after all filters + limit)
    if args.sample > 0 and len(articles) > args.sample:
        import random as _random
        articles = _random.sample(articles, args.sample)

    # Stats mode
    if args.stats:
        total = sum(v for v in stats.values() if v >= 0)
        failed = sum(1 for v in stats.values() if v == -1)
        avg_quality = sum(a.quality_score for a in articles) / len(articles) if articles else 0
        print(f"📊 Clawler Crawl Statistics")
        print(f"   Sources crawled: {len(stats)} ({failed} failed)")
        print(f"   Total raw articles: {total}")
        print(f"   After dedup + filters: {len(articles)}")
        print(f"   Avg quality score: {avg_quality:.3f}")
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

    # Count-only mode (for scripting)
    if args.count:
        print(len(articles))
        return

    # URLs-only mode (for piping)
    if args.urls_only:
        for a in articles:
            print(a.url)
        return

    # Titles-only mode
    if args.titles_only:
        for a in articles:
            print(a.title)
        return

    # Apply json-pretty shorthand
    if args.json_pretty:
        args.format = "json"

    # Apply json-compact shorthand
    if args.json_compact:
        args.format = "json"

    # Compact one-liner output
    if args.compact:
        from clawler.utils import relative_time
        lines = []
        for a in articles:
            age = relative_time(a.timestamp) if a.timestamp else "—"
            sc = f" ×{a.source_count}" if a.source_count > 1 else ""
            lines.append(f"[{a.source:15s}] [{age:>7s}]{sc}  {a.title}")
            lines.append(f"  {a.url}")
        output = "\n".join(lines) if lines else "No articles found."
    # Group-by output (text mode only, overrides formatter)
    elif args.group_by and args.format == "console":
        from collections import defaultdict
        groups = defaultdict(list)
        key_fn = (lambda a: a.category) if args.group_by == "category" else (lambda a: a.source)
        for a in articles:
            groups[key_fn(a)].append(a)
        lines = [f"🗞️  Clawler News Digest — {len(articles)} stories (grouped by {args.group_by})\n"]
        for group_name in sorted(groups.keys()):
            lines.append(f"\n━━━ {group_name.upper()} ({len(groups[group_name])}) ━━━")
            for i, a in enumerate(groups[group_name], 1):
                ts = a.timestamp.strftime("%Y-%m-%d %H:%M") if a.timestamp else "—"
                sc = f" [×{a.source_count}]" if a.source_count > 1 else ""
                lines.append(f"  {i}. {a.title}{sc}")
                lines.append(f"     {a.source} | {ts} | {a.url}")
        output = "\n".join(lines)
    else:
        # Format
        formatters = {
            "console": ConsoleFormatter, "jsonl": JSONLFormatter,
            "jsonfeed": JSONFeedFormatter,
            "atom": AtomFormatter, "rss": RSSFormatter, "markdown": MarkdownFormatter, "csv": CSVFormatter,
            "html": HTMLFormatter,
        }
        if args.format == "json":
            indent = None if args.json_compact else 2
            output = JSONFormatter(indent=indent).format(articles)
        else:
            output = formatters[args.format]().format(articles)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        if not args.quiet:
            print(f"✅ Wrote {len(articles)} articles to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Dedup stats
    if args.dedupe_stats and _dedup_stats:
        print(f"\n📊 {_dedup_stats.summary()}", file=sys.stderr)

    # Bookmark results
    if args.bookmark and articles:
        from clawler.bookmarks import add_bookmarks
        added = add_bookmarks(articles)
        if not args.quiet:
            print(f"📚 Bookmarked {added} new article(s)", file=sys.stderr)

    # Age distribution
    if args.age_distribution and articles:
        from datetime import datetime as _dt, timezone as _tz
        _now = _dt.now(tz=_tz.utc)
        buckets = {"<1h": 0, "1-6h": 0, "6-12h": 0, "12-24h": 0, "1-2d": 0, "2-7d": 0, ">7d": 0, "unknown": 0}
        for a in articles:
            if not a.timestamp:
                buckets["unknown"] += 1
                continue
            ts = a.timestamp if a.timestamp.tzinfo else a.timestamp.replace(tzinfo=_tz.utc)
            age_h = (_now - ts).total_seconds() / 3600
            if age_h < 1:
                buckets["<1h"] += 1
            elif age_h < 6:
                buckets["1-6h"] += 1
            elif age_h < 12:
                buckets["6-12h"] += 1
            elif age_h < 24:
                buckets["12-24h"] += 1
            elif age_h < 48:
                buckets["1-2d"] += 1
            elif age_h < 168:
                buckets["2-7d"] += 1
            else:
                buckets[">7d"] += 1
        max_count = max(buckets.values()) if any(buckets.values()) else 1
        print(f"\n📊 Age Distribution ({len(articles)} articles):", file=sys.stderr)
        for label, count in buckets.items():
            if count == 0:
                continue
            bar = "█" * max(1, int(count / max_count * 30))
            print(f"  {label:>8s} | {bar} {count}", file=sys.stderr)

    # Domain breakdown
    if args.domains and articles:
        from urllib.parse import urlparse
        from collections import Counter
        domains = Counter(urlparse(a.url).netloc for a in articles)
        top_domains = domains.most_common(15)
        max_count = top_domains[0][1] if top_domains else 1
        print(f"\n🌐 Domain Breakdown ({len(domains)} unique domains):", file=sys.stderr)
        for domain, count in top_domains:
            bar = "█" * max(1, int(count / max_count * 25))
            print(f"  {domain:>35s} | {bar} {count}", file=sys.stderr)

    # Age statistics
    if args.age_stats and articles:
        from datetime import datetime as _dt, timezone as _tz
        _now = _dt.now(tz=_tz.utc)
        ages_h = []
        for a in articles:
            if a.timestamp:
                ts = a.timestamp if a.timestamp.tzinfo else a.timestamp.replace(tzinfo=_tz.utc)
                ages_h.append((_now - ts).total_seconds() / 3600)
        if ages_h:
            ages_h.sort()
            _min = ages_h[0]
            _max = ages_h[-1]
            _avg = sum(ages_h) / len(ages_h)
            _med = ages_h[len(ages_h) // 2]

            def _fmt_age(h):
                if h < 1:
                    return f"{h * 60:.0f}m"
                if h < 24:
                    return f"{h:.1f}h"
                return f"{h / 24:.1f}d"

            print(f"\n⏱️  Age Statistics ({len(ages_h)}/{len(articles)} with timestamps):", file=sys.stderr)
            print(f"   Newest: {_fmt_age(_min)}  |  Oldest: {_fmt_age(_max)}  |  Avg: {_fmt_age(_avg)}  |  Median: {_fmt_age(_med)}", file=sys.stderr)

    # Top sources breakdown
    if args.top_sources and articles:
        from collections import Counter
        src_counts = Counter(a.source for a in articles)
        top = src_counts.most_common(10)
        max_count = top[0][1] if top else 1
        print(f"\n📡 Top Sources ({len(src_counts)} total):", file=sys.stderr)
        for src_name, count in top:
            bar = "█" * max(1, int(count / max_count * 25))
            print(f"  {src_name:>30s} | {bar} {count}", file=sys.stderr)

    # Watch mode: repeat crawl at interval
    if args.watch:
        _watch_loop(args)


def _watch_loop(args):
    """Continuously re-run crawl at the specified interval.

    Builds an explicit argv list from the original sys.argv with --watch
    removed, so main() doesn't recurse back into _watch_loop.
    """
    import re as _re
    match = _re.match(r"^(\d+)\s*([mhs])$", args.watch.strip().lower())
    if not match:
        print(f"Error: Invalid --watch interval '{args.watch}'. Use e.g. 5m, 1h, 30s", file=sys.stderr)
        sys.exit(1)
    amount, unit = int(match.group(1)), match.group(2)
    seconds = {"s": 1, "m": 60, "h": 3600}[unit] * amount
    watch_val = args.watch

    # Build argv without --watch to prevent recursion
    raw = sys.argv[1:]
    clean_argv = []
    skip_next = False
    for i, arg in enumerate(raw):
        if skip_next:
            skip_next = False
            continue
        if arg == "--watch":
            skip_next = True  # skip the next arg (the interval value)
            continue
        if arg.startswith("--watch="):
            continue
        clean_argv.append(arg)

    if not args.quiet:
        print(f"\n⏰ Watch mode: refreshing every {watch_val}. Press Ctrl+C to stop.", file=sys.stderr)
    try:
        import time
        while True:
            time.sleep(seconds)
            if not args.quiet:
                print(f"\n🔄 Refreshing...", file=sys.stderr)
            main(argv=clean_argv)
    except KeyboardInterrupt:
        if not args.quiet:
            print("\n👋 Watch stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()
