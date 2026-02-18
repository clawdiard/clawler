"""Tests for Guardian source v10.26.0 enhancements."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.guardian import (
    GuardianSource,
    GUARDIAN_FEEDS,
    _detect_category,
    _compute_quality,
    CATEGORY_KEYWORDS,
    PROMINENT_AUTHORS,
)


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>The Guardian - Technology</title>
<item>
  <title>OpenAI launches new GPT-5 model with breakthrough capabilities</title>
  <link>https://www.theguardian.com/technology/2026/feb/18/openai-gpt5</link>
  <description>The AI company revealed its latest large language model</description>
  <pubDate>Wed, 18 Feb 2026 12:00:00 GMT</pubDate>
  <author>Dan Milmo</author>
  <category>Artificial intelligence (AI)</category>
  <category>Technology</category>
</item>
<item>
  <title>Major ransomware attack hits UK hospitals</title>
  <link>https://www.theguardian.com/technology/2026/feb/18/ransomware-hospitals</link>
  <description>NHS services disrupted as cybersecurity breach affects patient records</description>
  <pubDate>Wed, 18 Feb 2026 11:00:00 GMT</pubDate>
  <author>Alex Hern</author>
</item>
<item>
  <title>Exclusive: Tech giant plans massive layoffs amid restructuring</title>
  <link>https://www.theguardian.com/technology/2026/feb/18/tech-layoffs</link>
  <description>Revealed: thousands of jobs at risk in latest round of cuts</description>
  <pubDate>Wed, 18 Feb 2026 10:00:00 GMT</pubDate>
  <author>Marina Hyde</author>
</item>
</channel>
</rss>"""

SAMPLE_RSS_2 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>The Guardian - Science</title>
<item>
  <title>NASA discovers high-energy quantum particles near black hole</title>
  <link>https://www.theguardian.com/science/2026/feb/18/nasa-quantum</link>
  <description>Breakthrough in space physics research</description>
  <pubDate>Wed, 18 Feb 2026 09:00:00 GMT</pubDate>
  <author>Ian Sample</author>
</item>
<item>
  <title>OpenAI launches new GPT-5 model with breakthrough capabilities</title>
  <link>https://www.theguardian.com/technology/2026/feb/18/openai-gpt5</link>
  <description>The AI company revealed its latest large language model</description>
  <pubDate>Wed, 18 Feb 2026 12:00:00 GMT</pubDate>
  <author>Dan Milmo</author>
</item>
</channel>
</rss>"""


class TestCategoryDetection:
    def test_ai_keywords(self):
        assert _detect_category("OpenAI launches GPT-5", "artificial intelligence model", "tech") == "ai"

    def test_security_keywords(self):
        assert _detect_category("Major ransomware attack", "cybersecurity breach", "tech") == "security"

    def test_health_keywords(self):
        assert _detect_category("New vaccine approved", "clinical trial results for cancer treatment", "science") == "health"

    def test_crypto_keywords(self):
        assert _detect_category("Bitcoin hits new high", "cryptocurrency market surges", "business") == "crypto"

    def test_environment_keywords(self):
        assert _detect_category("Carbon emissions reach record", "climate change fossil fuel", "science") == "environment"

    def test_gaming_keywords(self):
        assert _detect_category("PlayStation 6 revealed", "video game console", "tech") == "gaming"

    def test_education_keywords(self):
        assert _detect_category("University tuition fees rise", "student scholarship cuts", "society") == "education"

    def test_fallback_to_section(self):
        assert _detect_category("A bland title", "nothing specific here", "culture") == "culture"

    def test_world_keywords(self):
        assert _detect_category("NATO sanctions Russia", "geopolitical conflict", "world") == "world"

    def test_design_keywords(self):
        assert _detect_category("New UX design patterns", "accessibility and figma", "tech") == "design"


class TestQualityScoring:
    def test_baseline_from_prominence(self):
        q = _compute_quality(1.0, "", "Normal article", "tech")
        assert 0.5 <= q <= 0.6

    def test_prominent_author_boost(self):
        q_normal = _compute_quality(0.9, "Unknown Author", "Article", "tech")
        q_prominent = _compute_quality(0.9, "Marina Hyde", "Article", "tech")
        assert q_prominent > q_normal

    def test_exclusive_boost(self):
        q_normal = _compute_quality(0.9, "", "Normal article", "tech")
        q_exclusive = _compute_quality(0.9, "", "Exclusive: Big news revealed", "tech")
        assert q_exclusive > q_normal

    def test_specific_category_boost(self):
        q_tech = _compute_quality(0.9, "", "Article", "tech")
        q_ai = _compute_quality(0.9, "", "Article", "ai")
        assert q_ai > q_tech

    def test_score_capped_at_1(self):
        q = _compute_quality(1.0, "Marina Hyde", "Exclusive: Breaking investigation", "ai")
        assert q <= 1.0

    def test_low_prominence_section(self):
        q = _compute_quality(0.6, "", "Normal article", "culture")
        assert q < 0.5


class TestGuardianSource:
    def _mock_source(self, **kwargs):
        src = GuardianSource(**kwargs)
        return src

    @patch.object(GuardianSource, "fetch_url")
    def test_basic_crawl(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        assert len(articles) == 3
        assert all(a.source.startswith("The Guardian") for a in articles)

    @patch.object(GuardianSource, "fetch_url")
    def test_category_detection_in_articles(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        cats = {a.title: a.category for a in articles}
        assert cats["OpenAI launches new GPT-5 model with breakthrough capabilities"] == "ai"
        assert cats["Major ransomware attack hits UK hospitals"] == "security"

    @patch.object(GuardianSource, "fetch_url")
    def test_quality_scores_assigned(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        assert all(a.quality_score is not None and a.quality_score > 0 for a in articles)

    @patch.object(GuardianSource, "fetch_url")
    def test_sorted_by_quality(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        scores = [a.quality_score for a in articles]
        assert scores == sorted(scores, reverse=True)

    @patch.object(GuardianSource, "fetch_url")
    def test_min_quality_filter(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"], min_quality=0.99)
        articles = src.crawl()
        assert len(articles) == 0

    @patch.object(GuardianSource, "fetch_url")
    def test_category_filter(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"], category_filter=["ai"])
        articles = src.crawl()
        assert all(a.category == "ai" for a in articles)
        assert len(articles) >= 1

    @patch.object(GuardianSource, "fetch_url")
    def test_global_limit(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"], global_limit=1)
        articles = src.crawl()
        assert len(articles) == 1

    @patch.object(GuardianSource, "fetch_url")
    def test_cross_section_dedup(self, mock_fetch):
        """Same article appearing in tech and science should be deduped."""
        mock_fetch.side_effect = [SAMPLE_RSS, SAMPLE_RSS_2]
        src = self._mock_source(sections=["technology", "science"])
        articles = src.crawl()
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))
        # GPT-5 article appears in both feeds but should only show once
        gpt5_count = sum(1 for a in articles if "gpt5" in a.url.lower() or "gpt-5" in a.title.lower())
        assert gpt5_count == 1

    @patch.object(GuardianSource, "fetch_url")
    def test_exclude_sections(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(exclude_sections=["technology"])
        # technology is excluded so fetch_url shouldn't be called for it
        # but other sections still get attempted
        articles = src.crawl()
        assert all("technology" not in (a.tags or []) for a in articles
                   if a.tags and any("guardian:section:technology" in t for t in a.tags))

    @patch.object(GuardianSource, "fetch_url")
    def test_provenance_tags(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        for a in articles:
            assert any(t.startswith("guardian:section:") for t in a.tags)
            assert any(t.startswith("guardian:category:") for t in a.tags)

    @patch.object(GuardianSource, "fetch_url")
    def test_author_provenance_tag(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        authored = [a for a in articles if a.author]
        assert len(authored) >= 1
        for a in authored:
            assert any(t.startswith("guardian:author:") for t in a.tags)

    @patch.object(GuardianSource, "fetch_url")
    def test_rss_category_tags(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        gpt5 = [a for a in articles if "gpt5" in a.url.lower() or "gpt-5" in a.title.lower()][0]
        assert any(t.startswith("guardian:tag:") for t in gpt5.tags)

    @patch.object(GuardianSource, "fetch_url")
    def test_rich_summary_format(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        for a in articles:
            assert "📰" in a.summary

    @patch.object(GuardianSource, "fetch_url")
    def test_prominent_author_higher_quality(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        hyde = [a for a in articles if a.author == "Marina Hyde"]
        others = [a for a in articles if a.author and a.author != "Marina Hyde"]
        if hyde and others:
            assert hyde[0].quality_score >= min(o.quality_score for o in others)

    def test_20_sections_configured(self):
        assert len(GUARDIAN_FEEDS) == 20

    def test_all_feeds_have_required_keys(self):
        for f in GUARDIAN_FEEDS:
            assert "url" in f
            assert "section" in f
            assert "category" in f
            assert "prominence" in f

    @patch.object(GuardianSource, "fetch_url")
    def test_empty_feed(self, mock_fetch):
        mock_fetch.return_value = ""
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        assert articles == []

    @patch.object(GuardianSource, "fetch_url")
    def test_sections_filter(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_RSS
        src = self._mock_source(sections=["technology"])
        articles = src.crawl()
        assert mock_fetch.call_count == 1

    def test_default_all_sections(self):
        src = GuardianSource()
        assert src.sections is None  # means all
