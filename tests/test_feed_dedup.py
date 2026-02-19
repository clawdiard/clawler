"""Ensure no duplicate feed URLs exist in the RSS source."""
from collections import Counter
from clawler.sources.rss import DEFAULT_FEEDS


def test_no_duplicate_feed_urls():
    """DEFAULT_FEEDS must not contain duplicate URLs."""
    urls = [f["url"] for f in DEFAULT_FEEDS]
    dupes = {u: c for u, c in Counter(urls).items() if c > 1}
    assert not dupes, f"Duplicate feed URLs found: {dupes}"


def test_feeds_have_required_keys():
    """Each feed entry must have url, source, and category."""
    for i, feed in enumerate(DEFAULT_FEEDS):
        assert "url" in feed, f"Feed {i} missing 'url'"
        assert "source" in feed, f"Feed {i} missing 'source'"
        assert "category" in feed, f"Feed {i} missing 'category'"
        assert feed["url"].startswith(("http://", "https://")), f"Feed {i} has invalid URL: {feed['url']}"


def test_feed_count_sanity():
    """Sanity check: we should have a substantial number of feeds."""
    assert len(DEFAULT_FEEDS) >= 400, f"Expected 400+ feeds, got {len(DEFAULT_FEEDS)}"
