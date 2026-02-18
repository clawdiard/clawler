"""Tests for 404 Media and ProPublica sources (v10.32.0)."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from clawler.sources.fourzerofourmedia import FourZeroFourMediaSource, _categorize, FEED_URL
from clawler.sources.propublica import ProPublicaSource, _categorize as pp_categorize
from clawler.registry import SOURCES, get_entry, build_sources


# ── Registry tests ──────────────────────────────────────────────────

def test_404media_in_registry():
    entry = get_entry("404media")
    assert entry is not None
    assert entry.display_name == "404 Media"
    cls = entry.load_class()
    assert cls is FourZeroFourMediaSource


def test_propublica_in_registry():
    entry = get_entry("propublica")
    assert entry is not None
    assert entry.display_name == "ProPublica"
    cls = entry.load_class()
    assert cls is ProPublicaSource


def test_total_sources_59():
    assert len(SOURCES) == 61


# ── 404 Media tests ────────────────────────────────────────────────

SAMPLE_404_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>404 Media</title>
  <item>
    <title>Hackers Are Exploiting a Flaw in Popular Router Firmware</title>
    <link>https://www.404media.co/hackers-router-firmware/</link>
    <description>A critical vulnerability in widely-used router firmware is being actively exploited.</description>
    <pubDate>Tue, 18 Feb 2026 12:00:00 GMT</pubDate>
    <author>Joseph Cox</author>
    <category>Hacking</category>
  </item>
  <item>
    <title>Inside the AI-Generated Deepfake Industry</title>
    <link>https://www.404media.co/ai-deepfake-industry/</link>
    <description>An investigation into the growing deepfake creation marketplace.</description>
    <pubDate>Mon, 17 Feb 2026 10:00:00 GMT</pubDate>
    <author>Emanuel Maiberg</author>
  </item>
  <item>
    <title>TikTok Quietly Changed Its Privacy Policy</title>
    <link>https://www.404media.co/tiktok-privacy-policy/</link>
    <description>Social media giant updated data collection terms with little fanfare.</description>
    <pubDate>Sun, 16 Feb 2026 08:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


def test_404media_crawl():
    src = FourZeroFourMediaSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_404_RSS):
        articles = src.crawl()
    assert len(articles) == 3
    assert articles[0].source == "404 Media"
    assert articles[0].title == "Hackers Are Exploiting a Flaw in Popular Router Firmware"
    assert articles[0].author == "Joseph Cox"
    assert "404media" in articles[0].tags


def test_404media_categorize():
    assert _categorize("Hackers breach database", "") == "cybersecurity"
    assert _categorize("New AI model released", "") == "ai"
    assert _categorize("Surveillance cameras everywhere", "") == "privacy"
    assert _categorize("TikTok viral trend", "") == "internet_culture"
    assert _categorize("FCC regulation update", "") == "policy"
    assert _categorize("New gadget review", "") == "tech"


def test_404media_category_filter():
    src = FourZeroFourMediaSource(categories=["cybersecurity"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_404_RSS):
        articles = src.crawl()
    assert len(articles) == 1
    assert articles[0].category == "cybersecurity"


def test_404media_limit():
    src = FourZeroFourMediaSource(limit=1)
    with patch.object(src, "fetch_url", return_value=SAMPLE_404_RSS):
        articles = src.crawl()
    assert len(articles) == 1


def test_404media_empty_feed():
    src = FourZeroFourMediaSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


# ── ProPublica tests ────────────────────────────────────────────────

SAMPLE_PP_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>ProPublica</title>
  <item>
    <title>How Hospitals Are Overcharging Medicare Patients</title>
    <link>https://www.propublica.org/article/hospitals-overcharging</link>
    <description>An investigation into billing practices at major hospital systems.</description>
    <pubDate>Tue, 18 Feb 2026 14:00:00 GMT</pubDate>
    <author>ProPublica Staff</author>
  </item>
  <item>
    <title>The Algorithm That Decides Who Gets Bail</title>
    <link>https://www.propublica.org/article/bail-algorithm</link>
    <description>Courts are using AI to make bail decisions with troubling accuracy gaps.</description>
    <pubDate>Mon, 17 Feb 2026 11:00:00 GMT</pubDate>
  </item>
</channel>
</rss>"""


def test_propublica_crawl():
    src = ProPublicaSource()
    with patch.object(src, "fetch_url", return_value=SAMPLE_PP_RSS):
        articles = src.crawl()
    assert len(articles) == 4  # 2 feeds × 2 articles each
    assert all("propublica" in a.tags for a in articles)
    assert articles[0].source.startswith("ProPublica")


def test_propublica_categorize():
    assert pp_categorize("Police brutality investigation", "") == "criminal_justice"
    assert pp_categorize("Hospital billing fraud", "") == "healthcare"
    assert pp_categorize("School funding cuts", "") == "education"
    assert pp_categorize("Climate change report", "") == "environment"
    assert pp_categorize("AI algorithm bias", "") == "tech"
    assert pp_categorize("Congressional lobbying", "") == "government"
    assert pp_categorize("Wall Street fraud case", "") == "finance"
    assert pp_categorize("Award-winning investigation", "") == "investigative"


def test_propublica_empty_feed():
    src = ProPublicaSource()
    with patch.object(src, "fetch_url", return_value=""):
        articles = src.crawl()
    assert articles == []


def test_propublica_category_filter():
    src = ProPublicaSource(categories=["healthcare"])
    with patch.object(src, "fetch_url", return_value=SAMPLE_PP_RSS):
        articles = src.crawl()
    assert all(a.category == "healthcare" for a in articles)
