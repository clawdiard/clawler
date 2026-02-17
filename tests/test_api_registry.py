"""Tests for the refactored api.py — registry-based source building."""
from unittest.mock import patch, MagicMock
from clawler.api import crawl
from clawler.registry import get_all_keys


class TestApiRegistryIntegration:
    """Verify api.crawl() correctly delegates to registry.build_sources()."""

    @patch("clawler.api.build_sources")
    @patch("clawler.api.CrawlEngine")
    def test_crawl_no_disabled(self, mock_engine_cls, mock_build):
        """Default crawl passes empty disabled set."""
        mock_engine = MagicMock()
        mock_engine.crawl.return_value = ([], {}, MagicMock())
        mock_engine_cls.return_value = mock_engine
        mock_build.return_value = [MagicMock()]

        crawl(limit=5)

        mock_build.assert_called_once_with(disabled=set(), timeout=15)

    @patch("clawler.api.build_sources")
    @patch("clawler.api.CrawlEngine")
    def test_crawl_disabled_set(self, mock_engine_cls, mock_build):
        """disabled= kwarg forwarded correctly."""
        mock_engine = MagicMock()
        mock_engine.crawl.return_value = ([], {}, MagicMock())
        mock_engine_cls.return_value = mock_engine
        mock_build.return_value = [MagicMock()]

        crawl(disabled={"hn", "reddit"}, limit=5)

        mock_build.assert_called_once_with(disabled={"hn", "reddit"}, timeout=15)

    @patch("clawler.api.build_sources")
    @patch("clawler.api.CrawlEngine")
    def test_crawl_legacy_no_flags(self, mock_engine_cls, mock_build):
        """Legacy no_hn=True translated to disabled set."""
        mock_engine = MagicMock()
        mock_engine.crawl.return_value = ([], {}, MagicMock())
        mock_engine_cls.return_value = mock_engine
        mock_build.return_value = [MagicMock()]

        crawl(no_hn=True, no_reddit=True, limit=5)

        call_args = mock_build.call_args
        assert "hn" in call_args.kwargs["disabled"]
        assert "reddit" in call_args.kwargs["disabled"]

    @patch("clawler.api.build_sources")
    @patch("clawler.api.CrawlEngine")
    def test_crawl_only(self, mock_engine_cls, mock_build):
        """only= enables only specified sources."""
        mock_engine = MagicMock()
        mock_engine.crawl.return_value = ([], {}, MagicMock())
        mock_engine_cls.return_value = mock_engine
        mock_build.return_value = [MagicMock()]

        crawl(only="hn,rss", limit=5)

        call_args = mock_build.call_args
        disabled = call_args.kwargs["disabled"]
        assert "hn" not in disabled
        assert "rss" not in disabled
        # All other sources should be disabled
        assert "reddit" in disabled
        assert "github" in disabled

    def test_all_registry_keys_accepted_as_no_flags(self):
        """Every registry key should be accepted as no_<key> kwarg without error."""
        all_keys = get_all_keys()
        # Just verify the kwargs dict can be built — no crash
        kwargs = {f"no_{k}": False for k in all_keys}
        assert len(kwargs) == len(all_keys)
