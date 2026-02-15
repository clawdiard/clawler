"""Tests for Reddit source."""
from unittest.mock import patch
from clawler.sources.reddit import RedditSource, SUBREDDIT_CATEGORIES


SAMPLE_REDDIT_JSON = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "Python 4.0 Released",
                    "url": "https://python.org/blog/4.0",
                    "permalink": "/r/programming/comments/abc123/python_40_released/",
                    "author": "dev_user",
                    "score": 5000,
                    "num_comments": 800,
                    "upvote_ratio": 0.95,
                    "created_utc": 1739600000,
                    "link_flair_text": "Release",
                    "over_18": False,
                    "is_self": False,
                    "selftext": "",
                    "subreddit": "programming",
                }
            },
            {
                "data": {
                    "title": "NSFW Post",
                    "url": "https://example.com/nsfw",
                    "permalink": "/r/programming/comments/def456/nsfw_post/",
                    "author": "user2",
                    "score": 100,
                    "num_comments": 10,
                    "upvote_ratio": 0.8,
                    "created_utc": 1739600000,
                    "over_18": True,
                    "is_self": False,
                    "selftext": "",
                    "subreddit": "programming",
                }
            },
        ]
    }
}


def test_reddit_crawl():
    """Test Reddit source extracts articles correctly."""
    src = RedditSource(subreddits=["programming"], limit=5)
    with patch.object(src, "fetch_json", return_value=SAMPLE_REDDIT_JSON):
        articles = src.crawl()

    # NSFW filtered out by default
    assert len(articles) == 1
    assert articles[0].title == "Python 4.0 Released"
    assert articles[0].url == "https://python.org/blog/4.0"
    assert articles[0].author == "dev_user"


def test_reddit_allow_nsfw():
    """Test Reddit source includes NSFW when allowed."""
    src = RedditSource(subreddits=["programming"], limit=5, allow_nsfw=True)
    with patch.object(src, "fetch_json", return_value=SAMPLE_REDDIT_JSON):
        articles = src.crawl()

    assert len(articles) == 2


def test_reddit_empty_response():
    """Test Reddit handles empty response."""
    src = RedditSource(subreddits=["programming"])
    with patch.object(src, "fetch_json", return_value=None):
        articles = src.crawl()
    assert articles == []


def test_reddit_build_url():
    """Test URL building with sort and time filter."""
    src = RedditSource(sort="top", time_filter="week")
    url = src._build_url("programming")
    assert "programming/top.json" in url
    assert "t=week" in url


def test_subreddit_categories_complete():
    """Test that all default subreddits have category mappings."""
    from clawler.sources.reddit import DEFAULT_SUBREDDITS
    for sub in DEFAULT_SUBREDDITS:
        assert sub in SUBREDDIT_CATEGORIES, f"Missing category mapping for r/{sub}"
