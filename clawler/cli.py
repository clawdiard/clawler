"""CLI entry point for Clawler."""
import argparse
import logging
import sys
from clawler.engine import CrawlEngine
from clawler.formatters import ConsoleFormatter, JSONFormatter, MarkdownFormatter


def main():
    parser = argparse.ArgumentParser(
        prog="clawler",
        description="🗞️ Clawler — Advanced news crawling service",
    )
    parser.add_argument("-f", "--format", choices=["console", "json", "markdown"], default="console",
                        help="Output format (default: console)")
    parser.add_argument("-n", "--limit", type=int, default=50,
                        help="Max articles to display (default: 50)")
    parser.add_argument("--category", choices=["tech", "world", "science", "business", "all"], default="all",
                        help="Filter by category")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--no-reddit", action="store_true", help="Skip Reddit source")
    parser.add_argument("--no-hn", action="store_true", help="Skip Hacker News source")
    parser.add_argument("--no-rss", action="store_true", help="Skip RSS feeds")

    args = parser.parse_args()

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
    print("🕷️  Crawling news sources...", file=sys.stderr)
    articles = engine.crawl()

    # Filter by category
    if args.category != "all":
        articles = [a for a in articles if a.category == args.category]

    # Limit
    articles = articles[:args.limit]

    # Format
    formatters = {"console": ConsoleFormatter, "json": JSONFormatter, "markdown": MarkdownFormatter}
    output = formatters[args.format]().format(articles)
    print(output)


if __name__ == "__main__":
    main()
