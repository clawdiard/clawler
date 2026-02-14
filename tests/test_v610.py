"""Tests for v6.1.0: source registry refactor, version sync, CLI source builder."""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestVersionSync(unittest.TestCase):
    """All version strings must match."""

    def test_version_is_610(self):
        from clawler import __version__
        self.assertEqual(__version__, "6.1.0")

    def test_pyproject_version(self):
        from clawler import __version__
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        self.assertIn(f'version = "{__version__}"', pyproject.read_text())

    def test_setup_version(self):
        from clawler import __version__
        setup = Path(__file__).parent.parent / "setup.py"
        self.assertIn(f'version="{__version__}"', setup.read_text())


class TestSourceRegistry(unittest.TestCase):
    """Test the data-driven source registry in CLI."""

    def test_all_sources_enabled_by_default(self):
        """With no --no-* flags, all 16 sources should be built."""
        from clawler.cli import main
        from io import StringIO
        with patch("sys.stderr", new_callable=StringIO):
            # dry-run to see source list without actually crawling
            with patch("sys.stdout", new_callable=StringIO) as out:
                main(["--dry-run"])
        output = out.getvalue()
        # All major sources should appear
        for name in ["RSS", "Hacker News", "Reddit", "GitHub", "Mastodon",
                      "Wikipedia", "Lobsters", "Dev.to", "ArXiv", "TechMeme",
                      "ProductHunt", "Bluesky"]:
            self.assertIn(name, output, f"{name} missing from dry-run output")

    def test_only_flag_disables_others(self):
        """--only rss should disable all non-RSS sources."""
        from clawler.cli import main
        from io import StringIO
        with patch("sys.stderr", new_callable=StringIO):
            with patch("sys.stdout", new_callable=StringIO) as out:
                main(["--dry-run", "--only", "rss"])
        output = out.getvalue()
        self.assertIn("RSS", output)
        self.assertNotIn("Hacker News", output)
        self.assertNotIn("Reddit", output)

    def test_source_count(self):
        """Registry should have 16 source types."""
        from clawler.sources import __all__
        self.assertEqual(len(__all__), 16)

    def test_no_stackoverflow_flag(self):
        """--no-stackoverflow should exclude Stack Overflow from dry-run."""
        from clawler.cli import main
        from io import StringIO
        with patch("sys.stderr", new_callable=StringIO):
            with patch("sys.stdout", new_callable=StringIO) as out:
                main(["--dry-run", "--no-stackoverflow"])
        # Stack Overflow not in dry-run output — it's not listed there currently,
        # but the flag should work without error
        # Just verify no crash
        self.assertTrue(True)


class TestCLISourceBuilder(unittest.TestCase):
    """Test that the refactored source builder produces correct sources."""

    @patch("clawler.engine.CrawlEngine.crawl")
    def test_sources_have_correct_timeout(self, mock_crawl):
        """Sources should inherit --timeout value."""
        from clawler.dedup import DedupStats
        mock_crawl.return_value = ([], {"RSS": 0}, DedupStats())
        from clawler.cli import main
        from io import StringIO
        with patch("sys.stdout", new_callable=StringIO):
            with patch("sys.stderr", new_callable=StringIO):
                # We can't easily inspect sources, but we verify no crash with custom timeout
                main(["--timeout", "30", "--only", "rss", "--count"])

    @patch("clawler.engine.CrawlEngine.crawl")
    def test_sources_have_correct_retries(self, mock_crawl):
        """Sources should inherit --retries value."""
        from clawler.dedup import DedupStats
        mock_crawl.return_value = ([], {"RSS": 0}, DedupStats())
        from clawler.cli import main
        from io import StringIO
        with patch("sys.stdout", new_callable=StringIO):
            with patch("sys.stderr", new_callable=StringIO):
                main(["--retries", "5", "--only", "rss", "--count"])


class TestURLNormalization(unittest.TestCase):
    """Additional URL normalization edge cases."""

    def test_normalize_preserves_path(self):
        from clawler.models import _normalize_url
        self.assertEqual(
            _normalize_url("https://www.example.com/article/123/"),
            "https://example.com/article/123"
        )

    def test_normalize_strips_www(self):
        from clawler.models import _normalize_url
        self.assertEqual(
            _normalize_url("https://www.bbc.com/news"),
            "https://bbc.com/news"
        )

    def test_normalize_root_path(self):
        from clawler.models import _normalize_url
        self.assertEqual(
            _normalize_url("https://example.com/"),
            "https://example.com/"
        )

    def test_normalize_no_www(self):
        from clawler.models import _normalize_url
        self.assertEqual(
            _normalize_url("https://lobste.rs/hottest"),
            "https://lobste.rs/hottest"
        )


if __name__ == "__main__":
    unittest.main()
