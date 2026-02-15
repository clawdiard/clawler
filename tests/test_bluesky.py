"""Tests for Bluesky source."""
from unittest.mock import patch
from clawler.sources.bluesky import BlueskySource, _guess_category


SAMPLE_FEED_RESPONSE = {
    "feed": [
        {
            "post": {
                "uri": "at://did:plc:abc123/app.bsky.feed.post/xyz789",
                "record": {"createdAt": "2026-02-15T12:00:00Z"},
                "embed": {
                    "$type": "app.bsky.embed.external#view",
                    "external": {
                        "uri": "https://example.com/cool-article",
                        "title": "Cool AI Article",
                        "description": "An article about machine learning breakthroughs",
                    },
                },
                "author": {
                    "handle": "alice.bsky.social",
                    "displayName": "Alice",
                },
                "likeCount": 42,
                "repostCount": 10,
                "replyCount": 5,
            }
        },
        {
            "post": {
                "uri": "at://did:plc:def456/app.bsky.feed.post/uvw000",
                "record": {"createdAt": "2026-02-15T11:00:00Z"},
                "embed": {
                    "$type": "app.bsky.embed.external#view",
                    "external": {
                        "uri": "https://bsky.app/internal-link",
                        "title": "Internal Link",
                        "description": "Should be skipped",
                    },
                },
                "author": {"handle": "bob.bsky.social", "displayName": "Bob"},
                "likeCount": 5,
                "repostCount": 0,
                "replyCount": 0,
            }
        },
        {
            "post": {
                "uri": "at://did:plc:ghi789/app.bsky.feed.post/rst111",
                "record": {"createdAt": "2026-02-15T10:00:00Z"},
                "embed": {"$type": "app.bsky.embed.images#view"},
                "author": {"handle": "carol.bsky.social"},
                "likeCount": 100,
                "repostCount": 50,
                "replyCount": 20,
            }
        },
    ]
}


def test_bluesky_crawl():
    """Test Bluesky source extracts articles from external link embeds."""
    src = BlueskySource(limit=10)
    with patch.object(src, "fetch_json", return_value=SAMPLE_FEED_RESPONSE):
        articles = src.crawl()

    # Only 1 article: internal bsky link skipped, image-only post skipped
    assert len(articles) == 1
    assert articles[0].title == "Cool AI Article"
    assert articles[0].url == "https://example.com/cool-article"
    assert articles[0].author == "Alice"
    assert articles[0].timestamp is not None
    assert "bluesky" in articles[0].tags


def test_bluesky_empty_response():
    """Test Bluesky handles no data gracefully."""
    src = BlueskySource()
    with patch.object(src, "fetch_json", return_value=None):
        articles = src.crawl()
    assert articles == []


def test_guess_category():
    assert _guess_category("New AI model released", "") == "tech"
    assert _guess_category("Climate research findings", "") == "science"
    assert _guess_category("Stock market crash", "economy") == "business"
    assert _guess_category("Major data breach", "vulnerability") == "security"
    assert _guess_category("A nice day", "") == "general"
