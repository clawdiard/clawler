"""Tests for enhanced EchoJS source (v10.60.0)."""
import pytest
from unittest.mock import patch, MagicMock
from clawler.sources.echojs import (
    EchoJSSource,
    _classify_category,
    _quality_score,
    _extract_tags,
    ECHOJS_API,
    ECHOJS_TOP_API,
)


class TestClassifyCategory:
    def test_react_is_tech(self):
        assert _classify_category("Building components with React 19") == "tech"

    def test_security_keyword(self):
        assert _classify_category("New XSS vulnerability in popular library") == "security"

    def test_startup_is_business(self):
        assert _classify_category("How my startup raised seed funding") == "business"

    def test_default_is_tech(self):
        assert _classify_category("Some random news article") == "tech"

    def test_case_insensitive(self):
        assert _classify_category("TYPESCRIPT 6.0 Released") == "tech"


class TestQualityScore:
    def test_high_votes(self):
        assert _quality_score(60, 0) == 1.0

    def test_medium_votes(self):
        assert _quality_score(25, 0) == 0.85

    def test_low_votes(self):
        assert _quality_score(3, 0) == 0.4

    def test_negative_score(self):
        score = _quality_score(2, 10)
        assert score == 0.3

    def test_net_score_matters(self):
        # 30 up, 5 down = 25 net → 0.85
        assert _quality_score(30, 5) == 0.85


class TestExtractTags:
    def test_always_has_base_tags(self):
        tags = _extract_tags("Hello world")
        assert "echojs:javascript" in tags
        assert "echojs:webdev" in tags

    def test_react_tag(self):
        tags = _extract_tags("React Server Components deep dive")
        assert "echojs:react" in tags

    def test_multiple_tags(self):
        tags = _extract_tags("Building a TypeScript AI assistant with Vite")
        assert "echojs:typescript" in tags
        assert "echojs:ai" in tags
        assert "echojs:vite" in tags

    def test_max_tags(self):
        tags = _extract_tags("react vue angular svelte node deno bun typescript css wasm")
        assert len(tags) <= 8


class TestEchoJSSource:
    def test_init_defaults(self):
        src = EchoJSSource()
        assert src.limit == 30
        assert src.include_top is True

    def test_init_custom(self):
        src = EchoJSSource(limit=10, include_top=False)
        assert src.limit == 10
        assert src.include_top is False

    def test_name(self):
        assert EchoJSSource().name == "echojs"

    def test_parse_items_empty(self):
        src = EchoJSSource()
        assert src._parse_items({}, "Test") == []
        assert src._parse_items(None, "Test") == []
        assert src._parse_items({"news": []}, "Test") == []

    def test_parse_items_valid(self):
        src = EchoJSSource()
        data = {
            "news": [
                {
                    "title": "React 20 Released",
                    "url": "https://example.com/react20",
                    "atime": "1700000000",
                    "up": "15",
                    "down": "2",
                    "username": "testuser",
                    "id": "12345",
                }
            ]
        }
        articles = src._parse_items(data, "Latest")
        assert len(articles) == 1
        a = articles[0]
        assert "React 20" in a.title
        assert a.url == "https://example.com/react20"
        assert a.author == "testuser"
        assert a.category == "tech"
        assert a.discussion_url == "https://www.echojs.com/news/12345"
        assert "echojs:react" in a.tags

    def test_parse_items_skips_no_title(self):
        src = EchoJSSource()
        data = {"news": [{"title": "", "url": "https://example.com"}]}
        assert src._parse_items(data, "Test") == []

    def test_crawl_deduplicates(self):
        src = EchoJSSource(include_top=True)
        same_item = {
            "news": [
                {"title": "Dupe", "url": "https://example.com/same", "atime": "1700000000", "up": "5", "down": "0", "username": "u", "id": "1"}
            ]
        }
        with patch.object(src, "fetch_json", return_value=same_item):
            articles = src.crawl()
            # Same URL from both latest and top → should appear once
            assert len(articles) == 1


class TestEchoJSDualFeed:
    def test_top_disabled(self):
        src = EchoJSSource(include_top=False)
        call_count = 0

        def mock_fetch(url):
            nonlocal call_count
            call_count += 1
            return {"news": [{"title": "Test", "url": f"https://example.com/{call_count}", "atime": "1700000000", "up": "1", "down": "0", "username": "u", "id": str(call_count)}]}

        with patch.object(src, "fetch_json", side_effect=mock_fetch):
            articles = src.crawl()
            assert call_count == 1  # Only latest, not top
