"""Tests for v10.71.0 fixes."""
import pytest


def test_version_sync():
    """__init__ and setup.py versions must match."""
    from clawler import __version__
    import ast
    from pathlib import Path

    setup_path = Path(__file__).parent.parent / "setup.py"
    tree = ast.parse(setup_path.read_text())
    setup_version = None
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "version":
            if isinstance(node.value, ast.Constant):
                setup_version = node.value.value
    assert setup_version is not None, "Could not find version in setup.py"
    assert __version__ == setup_version, f"__init__.py ({__version__}) != setup.py ({setup_version})"


def test_lazy_headers_copy():
    """_LazyHeaders must support .copy() for requests compatibility."""
    from clawler.sources.base import HEADERS
    copied = HEADERS.copy()
    assert isinstance(copied, dict)
    assert "User-Agent" in copied


def test_lazy_headers_get():
    """_LazyHeaders must support .get()."""
    from clawler.sources.base import HEADERS
    ua = HEADERS.get("User-Agent")
    assert ua is not None and "Clawler" in ua
    assert HEADERS.get("nonexistent", "default") == "default"


def test_lazy_headers_merge():
    """_LazyHeaders must support {**HEADERS, ...} merge."""
    from clawler.sources.base import HEADERS
    merged = {**HEADERS, "Accept": "text/html"}
    assert "User-Agent" in merged
    assert merged["Accept"] == "text/html"


def test_health_modifier_exact_match():
    """Health modifier should use exact matching, not substring."""
    from clawler.health import HealthTracker
    tracker = HealthTracker()
    tracker.data = {
        "NPR": {"total_crawls": 10, "failures": 8, "total_articles": 5},
        "CNPR_Custom": {"total_crawls": 10, "failures": 0, "total_articles": 100},
    }
    # NPR has 80% failure rate → should get 0.5 modifier
    assert tracker.get_health_modifier("NPR") == 0.5
    # An unrelated source should get 1.0, not match NPR via substring
    assert tracker.get_health_modifier("SomeSource") == 1.0


def test_health_modifier_case_insensitive():
    """Health modifier should match case-insensitively."""
    from clawler.health import HealthTracker
    tracker = HealthTracker()
    tracker.data = {
        "Hacker News": {"total_crawls": 10, "failures": 5, "total_articles": 50},
    }
    assert tracker.get_health_modifier("hacker news") == 0.8
