"""Tests for sources that were missing dedicated test coverage.

Covers: devto, echojs, freecodecamp, hackernoon, hashnode, indiehackers,
lemmy, lobsters, mastodon, pinboard, producthunt, rss, slashdot,
stackoverflow, substack, techmeme, theverge, tildes, wikipedia, wired, infoq
"""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from clawler.models import Article


# ── TechMeme ─────────────────────────────────────────────────────────────────

def test_techmeme_crawl():
    from clawler.sources.techmeme import TechMemeSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Big Tech News</title>
        <link>https://example.com/big-tech</link>
        <description>Summary of big tech news</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = TechMemeSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].title == "Big Tech News"
    assert articles[0].source == "TechMeme"
    assert articles[0].category == "tech"


def test_techmeme_empty():
    from clawler.sources.techmeme import TechMemeSource
    src = TechMemeSource()
    with patch.object(src, "fetch_url", return_value=""):
        assert src.crawl() == []


# ── Dev.to ───────────────────────────────────────────────────────────────────

def test_devto_crawl():
    from clawler.sources.devto import DevToSource

    fake_articles = [
        {
            "title": "Building an AI Agent",
            "url": "https://dev.to/user/ai-agent",
            "description": "How to build an AI agent",
            "published_at": "2026-02-17T01:00:00Z",
            "tag_list": ["ai", "python"],
            "user": {"name": "TestDev"},
            "positive_reactions_count": 50,
            "comments_count": 10,
            "reading_time_minutes": 5,
        }
    ]

    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=fake_articles):
        articles = src.crawl()
    assert len(articles) >= 1
    assert "AI Agent" in articles[0].title


def test_devto_empty():
    from clawler.sources.devto import DevToSource
    src = DevToSource()
    with patch.object(src, "fetch_json", return_value=None):
        assert src.crawl() == []


# ── Lobsters ─────────────────────────────────────────────────────────────────

def test_lobsters_crawl():
    from clawler.sources.lobsters import LobstersSource

    fake_stories = [
        {
            "title": "Rust Memory Safety",
            "url": "https://example.com/rust",
            "short_id_url": "https://lobste.rs/s/abc123",
            "description": "About Rust memory safety",
            "created_at": "2026-02-17T01:00:00Z",
            "submitter_user": {"username": "rustfan"},
            "tags": ["rust", "programming"],
            "score": 25,
            "comment_count": 5,
        }
    ]

    src = LobstersSource()
    with patch.object(src, "fetch_json", return_value=fake_stories):
        articles = src.crawl()
    assert len(articles) >= 1
    assert "Rust" in articles[0].title


# ── Wikipedia ────────────────────────────────────────────────────────────────

def test_wikipedia_source_name():
    from clawler.sources.wikipedia import WikipediaCurrentEventsSource
    src = WikipediaCurrentEventsSource()
    assert src.name == "wikipedia"


# ── ProductHunt ──────────────────────────────────────────────────────────────

def test_producthunt_crawl():
    from clawler.sources.producthunt import ProductHuntSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Cool AI Tool</title>
        <link>https://producthunt.com/posts/cool-ai</link>
        <description>An AI-powered tool</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = ProductHuntSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].title == "Cool AI Tool"


# ── Slashdot ─────────────────────────────────────────────────────────────────

def test_slashdot_crawl():
    from clawler.sources.slashdot import SlashdotSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Linux Kernel 7.0 Released</title>
        <link>https://slashdot.org/story/linux-7</link>
        <description>The new Linux kernel is here</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = SlashdotSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1
    assert "Linux" in articles[0].title


# ── EchoJS ───────────────────────────────────────────────────────────────────

def test_echojs_crawl():
    from clawler.sources.echojs import EchoJSSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>New JavaScript Framework</title>
        <link>https://echojs.com/news/1234</link>
        <description>Yet another JS framework</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = EchoJSSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── Hashnode ─────────────────────────────────────────────────────────────────

def test_hashnode_crawl():
    from clawler.sources.hashnode import HashnodeSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>React Best Practices 2026</title>
        <link>https://hashnode.com/post/react-2026</link>
        <description>Updated best practices</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = HashnodeSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── FreeCodeCamp ─────────────────────────────────────────────────────────────

def test_freecodecamp_crawl():
    from clawler.sources.freecodecamp import FreeCodeCampSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Learn Python in 2026</title>
        <link>https://freecodecamp.org/learn-python</link>
        <description>A guide to Python</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = FreeCodeCampSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── Changelog ────────────────────────────────────────────────────────────────

def test_changelog_crawl():
    from clawler.sources.changelog import ChangelogSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Open Source Update</title>
        <link>https://changelog.com/episode/123</link>
        <description>Latest in open source</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = ChangelogSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── HackerNoon ───────────────────────────────────────────────────────────────

def test_hackernoon_crawl():
    from clawler.sources.hackernoon import HackerNoonSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>The Future of Web3</title>
        <link>https://hackernoon.com/future-web3</link>
        <description>Exploring web3 trends</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = HackerNoonSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── Substack ─────────────────────────────────────────────────────────────────

def test_substack_crawl():
    from clawler.sources.substack import SubstackSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Newsletter Deep Dive</title>
        <link>https://example.substack.com/p/deep-dive</link>
        <description>An in-depth analysis</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = SubstackSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── Wired ────────────────────────────────────────────────────────────────────

def test_wired_crawl():
    from clawler.sources.wired import WiredSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>The AI Revolution</title>
        <link>https://wired.com/ai-revolution</link>
        <description>How AI is changing everything</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = WiredSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── The Verge ────────────────────────────────────────────────────────────────

def test_theverge_crawl():
    from clawler.sources.theverge import TheVergeSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Apple Vision Pro Update</title>
        <link>https://theverge.com/apple-vision</link>
        <description>Apple updates Vision Pro</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = TheVergeSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── Stack Overflow ───────────────────────────────────────────────────────────

def test_stackoverflow_crawl():
    from clawler.sources.stackoverflow import StackOverflowSource

    fake_response = {
        "items": [
            {
                "title": "How to use async/await in Python?",
                "link": "https://stackoverflow.com/q/12345",
                "score": 42,
                "answer_count": 5,
                "view_count": 1000,
                "tags": ["python", "async"],
                "creation_date": 1739750400,
                "owner": {"display_name": "coder123"},
            }
        ]
    }

    src = StackOverflowSource()
    with patch.object(src, "fetch_json", return_value=fake_response):
        articles = src.crawl()
    assert len(articles) >= 1
    assert "async" in articles[0].title.lower()


# ── Pinboard ─────────────────────────────────────────────────────────────────

def test_pinboard_source_name():
    from clawler.sources.pinboard import PinboardSource
    src = PinboardSource()
    assert src.name == "Pinboard Popular"


# ── Indie Hackers ────────────────────────────────────────────────────────────

def test_indiehackers_source_name():
    from clawler.sources.indiehackers import IndieHackersSource
    src = IndieHackersSource()
    assert src.name == "Indie Hackers"


# ── Tildes ───────────────────────────────────────────────────────────────────

def test_tildes_source_name():
    from clawler.sources.tildes import TildesSource
    src = TildesSource()
    assert src.name == "tildes"


# ── Lemmy ────────────────────────────────────────────────────────────────────

def test_lemmy_source_name():
    from clawler.sources.lemmy import LemmySource
    src = LemmySource()
    assert src.name == "lemmy"


# ── Mastodon ─────────────────────────────────────────────────────────────────

def test_mastodon_source_name():
    from clawler.sources.mastodon import MastodonSource
    src = MastodonSource()
    assert src.name == "mastodon"


# ── RSS (generic) ────────────────────────────────────────────────────────────

def test_rss_source_crawl():
    from clawler.sources.rss import RSSSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Generic RSS Article</title>
        <link>https://example.com/article</link>
        <description>A generic article</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = RSSSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── InfoQ ────────────────────────────────────────────────────────────────────

def test_infoq_crawl():
    from clawler.sources.infoq import InfoQSource

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Microservices at Scale</title>
        <link>https://infoq.com/articles/microservices</link>
        <description>Scaling microservices</description>
        <pubDate>Mon, 17 Feb 2026 01:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""

    src = InfoQSource()
    with patch.object(src, "fetch_url", return_value=rss):
        articles = src.crawl()
    assert len(articles) >= 1


# ── Sentiment module ─────────────────────────────────────────────────────────

def test_sentiment_classify():
    from clawler.sentiment import classify_tone
    a = Article(title="Breakthrough discovery cures disease", url="https://x.com", source="test")
    tone = classify_tone(a)
    assert tone in ("positive", "negative", "neutral")


# ── Language module ──────────────────────────────────────────────────────────

def test_language_detect():
    from clawler.language import detect_language
    a = Article(title="This is an English sentence about technology", url="https://x.com", source="test", summary="More English text here")
    lang = detect_language(a)
    assert lang == "en"


# ── Read time module ─────────────────────────────────────────────────────────

def test_read_time_estimate():
    from clawler.readtime import estimate_read_minutes
    text = "word " * 500
    a = Article(title=text, url="https://x.com", source="test", summary=text)
    minutes = estimate_read_minutes(a)
    assert minutes >= 1
