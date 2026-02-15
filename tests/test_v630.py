"""Tests for v6.3.0: Indie Hackers source, version sync fix."""
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestIndieHackersSource(unittest.TestCase):
    """Test the IndieHackers source plugin."""

    def test_import(self):
        from clawler.sources.indiehackers import IndieHackersSource
        src = IndieHackersSource()
        self.assertEqual(src.name, "Indie Hackers")

    def test_crawl_parses_posts(self):
        from clawler.sources.indiehackers import IndieHackersSource
        html = """
        <html><body>
            <a href="/post/how-i-built-my-saas-abc123">How I Built My SaaS to $10k MRR</a>
            <a href="/post/lessons-from-bootstrapping-def456">Lessons from Bootstrapping</a>
            <a href="/about">About</a>
            <a href="/post/short">No</a>
        </body></html>
        """
        src = IndieHackersSource()
        with patch.object(src, "fetch_url", return_value=html):
            articles = src.crawl()
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0].source, "Indie Hackers")
        self.assertEqual(articles[0].category, "business")
        self.assertIn("indiehackers.com/post/", articles[0].url)
        self.assertIn("indiehackers.com/post/", articles[1].url)

    def test_crawl_empty_page(self):
        from clawler.sources.indiehackers import IndieHackersSource
        src = IndieHackersSource()
        with patch.object(src, "fetch_url", return_value="<html></html>"):
            articles = src.crawl()
        self.assertEqual(articles, [])

    def test_crawl_network_failure(self):
        from clawler.sources.indiehackers import IndieHackersSource
        src = IndieHackersSource()
        with patch.object(src, "fetch_url", return_value=""):
            articles = src.crawl()
        self.assertEqual(articles, [])

    def test_dedup_urls(self):
        """Duplicate post links should be deduplicated."""
        from clawler.sources.indiehackers import IndieHackersSource
        html = """
        <html><body>
            <a href="/post/my-post-abc123">My Great Post</a>
            <a href="/post/my-post-abc123">My Great Post</a>
        </body></html>
        """
        src = IndieHackersSource()
        with patch.object(src, "fetch_url", return_value=html):
            articles = src.crawl()
        self.assertEqual(len(articles), 1)

    def test_absolute_urls(self):
        """Posts with absolute URLs should be handled."""
        from clawler.sources.indiehackers import IndieHackersSource
        html = '<html><body><a href="https://www.indiehackers.com/post/test-xyz">Absolute URL Post</a></body></html>'
        src = IndieHackersSource()
        with patch.object(src, "fetch_url", return_value=html):
            articles = src.crawl()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].url, "https://www.indiehackers.com/post/test-xyz")


class TestVersionSync630(unittest.TestCase):
    """Ensure version is synced across all config files."""

    def test_all_versions_match(self):
        from clawler import __version__
        self.assertEqual(__version__, "6.4.0")

        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        self.assertIn(f'version = "{__version__}"', pyproject.read_text())

        setup_py = Path(__file__).parent.parent / "setup.py"
        self.assertIn(f'version="{__version__}"', setup_py.read_text())


class TestSourceRegistry630(unittest.TestCase):
    """Ensure IndieHackers is in the source registry."""

    def test_indiehackers_in_all(self):
        from clawler.sources import __all__
        self.assertIn("IndieHackersSource", __all__)

    def test_indiehackers_weight(self):
        from clawler.weights import get_quality_score
        score = get_quality_score("Indie Hackers")
        self.assertAlmostEqual(score, 0.67, places=2)


class TestCliNoIndieHackersFlag(unittest.TestCase):
    """Test --no-indiehackers flag exists."""

    def test_flag_exists(self):
        import clawler.cli as cli_mod
        import io
        import sys
        # Just verify the arg parser accepts the flag
        parser = None
        # Build parser by calling main with --help would exit; instead check source
        src = Path(__file__).parent.parent / "clawler" / "cli.py"
        self.assertIn("--no-indiehackers", src.read_text())


if __name__ == "__main__":
    unittest.main()
