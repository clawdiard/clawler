"""Tests for Reddit source v10.64.0 — enhanced with quality scoring, keyword categories, filters."""
import math
from unittest.mock import patch, MagicMock
from clawler.sources.reddit import (
    RedditSource,
    _detect_keyword_category,
    _extract_domain,
    _human_count,
    _quality_score,
    DEFAULT_SUBREDDITS,
    SUBREDDIT_CATEGORIES,
)


# --- Helper: mock Reddit JSON response ---
def _mock_post(title="Test Post", score=100, num_comments=50, subreddit="technology",
               url="https://example.com/article", over_18=False, stickied=False,
               author="testuser", upvote_ratio=0.95, flair="", selftext="",
               is_self=False, created_utc=1700000000):
    return {
        "data": {
            "title": title,
            "score": score,
            "num_comments": num_comments,
            "subreddit": subreddit,
            "url": url,
            "over_18": over_18,
            "stickied": stickied,
            "author": author,
            "upvote_ratio": upvote_ratio,
            "link_flair_text": flair,
            "selftext": selftext,
            "is_self": is_self,
            "permalink": f"/r/{subreddit}/comments/abc123/test/",
            "created_utc": created_utc,
        }
    }


def _mock_response(posts):
    return {"data": {"children": posts}}


# --- Keyword category detection ---
def test_detect_ai_category():
    assert _detect_keyword_category("OpenAI releases GPT-5 model") == "ai"

def test_detect_security_category():
    assert _detect_keyword_category("Major ransomware attack hits hospitals") == "security"

def test_detect_crypto_category():
    assert _detect_keyword_category("Bitcoin and ethereum surge in crypto market") == "crypto"

def test_detect_health_category():
    assert _detect_keyword_category("FDA approves new cancer treatment drug") == "health"

def test_detect_no_category():
    assert _detect_keyword_category("A nice sunny day") is None

def test_detect_environment_category():
    assert _detect_keyword_category("Solar and wind energy break records for carbon reduction") == "environment"

def test_detect_gaming_category():
    assert _detect_keyword_category("Steam announces new indie game release") == "gaming"

def test_detect_world_category():
    assert _detect_keyword_category("NATO summit discusses sanctions and diplomacy") == "world"


# --- Domain extraction ---
def test_extract_domain():
    assert _extract_domain("https://www.nytimes.com/article") == "nytimes.com"

def test_extract_domain_no_www():
    assert _extract_domain("https://arstechnica.com/tech") == "arstechnica.com"

def test_extract_domain_reddit_self():
    assert _extract_domain("https://www.reddit.com/r/technology/comments/abc") is None

def test_extract_domain_redd_it():
    assert _extract_domain("https://redd.it/abc123") is None

def test_extract_domain_invalid():
    assert _extract_domain("not-a-url") is None


# --- Human-readable counts ---
def test_human_count_small():
    assert _human_count(42) == "42"

def test_human_count_thousands():
    assert _human_count(1500) == "1.5K"

def test_human_count_millions():
    assert _human_count(2300000) == "2.3M"


# --- Quality scoring ---
def test_quality_score_zero():
    q = _quality_score(0, 0, 0.0)
    assert q < 0.05

def test_quality_score_moderate():
    q = _quality_score(500, 50, 0.9)
    assert 0.3 < q < 0.7

def test_quality_score_high():
    q = _quality_score(10000, 1000, 0.95)
    assert q > 0.6

def test_quality_score_capped_at_one():
    q = _quality_score(1000000, 100000, 1.0)
    assert q <= 1.0


# --- RedditSource crawl ---
class TestRedditSource:

    def _crawl_with_posts(self, posts, **kwargs):
        src = RedditSource(subreddits=["technology"], **kwargs)
        with patch.object(src, "fetch_json", return_value=_mock_response(posts)):
            return src.crawl()

    def test_basic_crawl(self):
        posts = [_mock_post()]
        articles = self._crawl_with_posts(posts)
        assert len(articles) == 1
        assert articles[0].title == "Test Post"
        assert articles[0].quality_score > 0

    def test_stickied_filtered(self):
        posts = [_mock_post(stickied=True)]
        assert len(self._crawl_with_posts(posts)) == 0

    def test_nsfw_filtered_by_default(self):
        posts = [_mock_post(over_18=True)]
        assert len(self._crawl_with_posts(posts)) == 0

    def test_nsfw_allowed(self):
        posts = [_mock_post(over_18=True)]
        assert len(self._crawl_with_posts(posts, allow_nsfw=True)) == 1

    def test_min_score_filter(self):
        posts = [_mock_post(score=5), _mock_post(score=100, url="https://example.com/2")]
        articles = self._crawl_with_posts(posts, min_score=50)
        assert len(articles) == 1

    def test_min_comments_filter(self):
        posts = [_mock_post(num_comments=2), _mock_post(num_comments=100, url="https://example.com/2")]
        articles = self._crawl_with_posts(posts, min_comments=50)
        assert len(articles) == 1

    def test_min_quality_filter(self):
        posts = [_mock_post(score=1, num_comments=0)]
        articles = self._crawl_with_posts(posts, min_quality=0.5)
        assert len(articles) == 0

    def test_category_filter(self):
        posts = [_mock_post(title="OpenAI releases new LLM")]
        articles = self._crawl_with_posts(posts, category_filter=["security"])
        assert len(articles) == 0

    def test_category_filter_match(self):
        posts = [_mock_post(title="OpenAI releases new LLM")]
        articles = self._crawl_with_posts(posts, category_filter=["ai"])
        assert len(articles) == 1
        assert articles[0].category == "ai"

    def test_keyword_category_over_subreddit(self):
        posts = [_mock_post(title="Major ransomware attack on infrastructure")]
        articles = self._crawl_with_posts(posts)
        assert articles[0].category == "security"  # not "tech" from subreddit

    def test_subreddit_fallback_category(self):
        posts = [_mock_post(title="Something generic")]
        articles = self._crawl_with_posts(posts)
        assert articles[0].category == "tech"  # from SUBREDDIT_CATEGORIES

    def test_cross_subreddit_dedup(self):
        src = RedditSource(subreddits=["technology", "programming"])
        posts = [_mock_post(url="https://example.com/same")]
        with patch.object(src, "fetch_json", return_value=_mock_response(posts)):
            articles = src.crawl()
        # Same URL from two subs → only 1 article
        assert len(articles) == 1

    def test_domain_in_summary(self):
        posts = [_mock_post(url="https://www.nytimes.com/article")]
        articles = self._crawl_with_posts(posts)
        assert "nytimes.com" in articles[0].summary

    def test_provenance_tags(self):
        posts = [_mock_post(flair="Discussion", author="bob")]
        articles = self._crawl_with_posts(posts)
        tags = articles[0].tags
        assert "reddit:sub:technology" in tags
        assert "reddit:flair:discussion" in tags
        assert "reddit:author:bob" in tags

    def test_domain_tag(self):
        posts = [_mock_post(url="https://arstechnica.com/tech")]
        articles = self._crawl_with_posts(posts)
        assert "reddit:domain:arstechnica.com" in [t for t in articles[0].tags if t.startswith("reddit:domain:")]

    def test_self_post_tag(self):
        posts = [_mock_post(is_self=True, url="https://www.reddit.com/r/technology/comments/abc")]
        articles = self._crawl_with_posts(posts)
        assert "reddit:self-post" in articles[0].tags

    def test_discussion_tag_high_comments(self):
        posts = [_mock_post(num_comments=200)]
        articles = self._crawl_with_posts(posts)
        assert "reddit:has-discussion" in articles[0].tags

    def test_global_limit(self):
        posts = [
            _mock_post(url=f"https://example.com/{i}", score=100 - i)
            for i in range(10)
        ]
        articles = self._crawl_with_posts(posts, global_limit=3)
        assert len(articles) == 3

    def test_quality_sorted_output(self):
        posts = [
            _mock_post(url="https://example.com/low", score=5, num_comments=1),
            _mock_post(url="https://example.com/high", score=5000, num_comments=500),
        ]
        articles = self._crawl_with_posts(posts)
        assert articles[0].quality_score >= articles[1].quality_score

    def test_exclude_subreddits(self):
        src = RedditSource(subreddits=["technology", "news"], exclude_subreddits=["news"])
        call_count = 0
        original_subs = []

        def mock_fetch(url, **kwargs):
            original_subs.append(url)
            return _mock_response([_mock_post()])

        with patch.object(src, "fetch_json", side_effect=mock_fetch):
            articles = src.crawl()
        assert all("r/news/" not in u for u in original_subs)

    def test_flair_in_summary(self):
        posts = [_mock_post(flair="Breaking News")]
        articles = self._crawl_with_posts(posts)
        assert "[Breaking News]" in articles[0].summary

    def test_selftext_in_summary(self):
        posts = [_mock_post(selftext="This is my post content")]
        articles = self._crawl_with_posts(posts)
        assert "This is my post content" in articles[0].summary

    def test_author_in_summary(self):
        posts = [_mock_post(author="cooluser")]
        articles = self._crawl_with_posts(posts)
        assert "u/cooluser" in articles[0].summary

    def test_empty_title_skipped(self):
        posts = [_mock_post(title="")]
        assert len(self._crawl_with_posts(posts)) == 0

def test_default_subreddits_include_health():
    assert "health" in DEFAULT_SUBREDDITS

def test_default_subreddits_include_climate():
    assert "climate" in DEFAULT_SUBREDDITS
