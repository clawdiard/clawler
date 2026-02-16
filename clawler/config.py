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

_BOOL_FIELDS = {"verbose", "quiet", "no_reddit", "no_hn", "no_rss", "no_github",
                "no_mastodon", "no_wikipedia", "no_lobsters", "no_devto", "no_arxiv",
                "no_techmeme", "no_producthunt", "no_bluesky", "no_tildes", "no_lemmy",
                "no_slashdot", "no_stackoverflow", "no_pinboard", "no_indiehackers",
                "no_echojs", "no_hashnode", "no_freecodecamp", "no_changelog", "no_arstechnica",
                "stats", "check_feeds", "list_sources", "cache", "history",
                "digest", "fresh", "no_dedup", "dedupe_stats", "urls_only",
                "titles_only", "domains", "trending", "no_color", "show_read_time",
                "show_discussions", "json_compact", "json_pretty"}
_INT_FIELDS = {"limit", "timeout", "workers", "retries", "cache_ttl", "sample",
               "min_read", "max_read"}
_FLOAT_FIELDS = {"dedupe_threshold", "min_relevance", "min_quality"}
_STR_FIELDS = {"format", "category", "since", "output", "source", "search", "sort",
               "exclude_source", "exclude_category", "exclude_domain", "feeds",
               "export_opml", "import_opml", "profile", "interests", "tag", "lang",
               "exclude_lang", "tone", "watch", "group_by"}


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


def load_env_config() -> Dict[str, Any]:
    """Load config from CLAWLER_* environment variables.

    Maps CLAWLER_CATEGORY=tech → category=tech, CLAWLER_LIMIT=20 → limit=20, etc.
    Boolean vars: CLAWLER_QUIET=1, CLAWLER_NO_REDDIT=true, etc.
    """
    prefix = "CLAWLER_"
    config: Dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        field = key[len(prefix):].lower()
        if field in _BOOL_FIELDS:
            config[field] = value.lower() in ("1", "true", "yes", "on")
        elif field in _INT_FIELDS:
            try:
                config[field] = int(value)
            except ValueError:
                pass
        elif field in _FLOAT_FIELDS:
            try:
                config[field] = float(value)
            except ValueError:
                pass
        elif field in _STR_FIELDS:
            config[field] = value
    return config


def apply_config_defaults(parser, args):
    """Apply config file defaults to unset CLI args (CLI always wins).

    Priority: CLI flags > env vars (CLAWLER_*) > config files > parser defaults.
    """
    config = load_config()
    env_config = load_env_config()
    # Env vars override file config
    config.update(env_config)
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
