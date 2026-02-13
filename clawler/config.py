"""Config file support for Clawler.

Loads default CLI arguments from:
  1. ~/.clawler.yaml  (user-level)
  2. ./clawler.yaml   (project-level, overrides user-level)

Example config file:

    # ~/.clawler.yaml
    format: markdown
    limit: 25
    category: tech,science
    since: 6h
    quiet: true
    no_reddit: true
    dedupe_threshold: 0.8
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_BOOL_FIELDS = {"verbose", "quiet", "no_reddit", "no_hn", "no_rss", "stats", "check_feeds", "list_sources"}
_INT_FIELDS = {"limit", "timeout", "workers"}
_FLOAT_FIELDS = {"dedupe_threshold"}
_STR_FIELDS = {"format", "category", "since", "output", "source", "search", "sort",
               "exclude_source", "exclude_category", "feeds", "export_opml", "import_opml"}


def load_config() -> Dict[str, Any]:
    """Load config from YAML files, merging user + project level."""
    config: Dict[str, Any] = {}

    paths = [
        Path.home() / ".clawler.yaml",
        Path.home() / ".clawler.yml",
        Path("clawler.yaml"),
        Path("clawler.yml"),
    ]

    for p in paths:
        if p.is_file():
            try:
                import yaml
                with open(p, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    # Normalize keys: dashes → underscores
                    normalized = {k.replace("-", "_"): v for k, v in data.items()}
                    config.update(normalized)
                    logger.debug(f"[Config] Loaded {p}")
            except Exception as e:
                logger.warning(f"[Config] Failed to load {p}: {e}")

    return config


def apply_config_defaults(parser, args):
    """Apply config file defaults to unset CLI args (CLI always wins)."""
    config = load_config()
    if not config:
        return args

    for key, value in config.items():
        # Only apply if the CLI arg wasn't explicitly provided
        if not hasattr(args, key):
            continue
        current = getattr(args, key)
        # Detect if user provided the arg (compare to parser default)
        default = parser.get_default(key)
        if current != default:
            continue  # User explicitly set it, don't override

        # Type coerce
        if key in _BOOL_FIELDS:
            setattr(args, key, bool(value))
        elif key in _INT_FIELDS:
            setattr(args, key, int(value))
        elif key in _FLOAT_FIELDS:
            setattr(args, key, float(value))
        elif key in _STR_FIELDS:
            setattr(args, key, str(value))

    return args


_STARTER_CONFIG = """\
# Clawler configuration — customize your defaults here.
# CLI flags always override these values.
# See: https://github.com/clawdiard/clawler

# Output format: console, json, jsonl, jsonfeed, atom, markdown, csv, html
# format: console

# Max articles to display
# limit: 50

# Filter by category (comma-separated): tech, world, science, business, security, investigative, culture
# category: all

# Only show articles newer than this (e.g. 30m, 2h, 1d, 1w)
# since: 6h

# Suppress status messages
# quiet: false

# Skip specific sources
# no_reddit: false
# no_hn: false
# no_github: false

# Fuzzy dedup threshold (0.0-1.0, higher = stricter)
# dedupe_threshold: 0.75

# Max parallel workers
# workers: 6

# HTTP request timeout (seconds)
# timeout: 15
"""


def generate_starter_config() -> Path:
    """Write a starter config file to ~/.clawler.yaml (won't overwrite existing)."""
    path = Path.home() / ".clawler.yaml"
    if path.exists():
        path = Path.home() / ".clawler.yaml.new"
    path.write_text(_STARTER_CONFIG, encoding="utf-8")
    return path
