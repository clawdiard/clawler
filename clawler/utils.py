"""Shared utility functions."""
import re
from datetime import datetime, timedelta, timezone


def parse_since(value: str) -> datetime:
    """Parse a relative time string like '1h', '30m', '2d', '3M', '1y' or an
    ISO-8601 date/datetime into a UTC datetime.

    Supports:
      - Relative: 30s, 30m, 2h, 1d, 1w, 3M, 1y
      - Absolute: 2026-02-14, 2026-02-14T10:00:00, 2026-02-14T10:00:00Z

    Raises ValueError on invalid input.
    """
    stripped = value.strip()

    # Named periods
    named = {
        "yesterday": timedelta(days=1),
        "last-week": timedelta(weeks=1),
        "last-month": timedelta(days=30),
        "last-year": timedelta(days=365),
        "today": timedelta(hours=datetime.now(timezone.utc).hour,
                           minutes=datetime.now(timezone.utc).minute),
        "this-week": timedelta(days=datetime.now(timezone.utc).weekday()),
        "this-month": timedelta(days=datetime.now(timezone.utc).day - 1),
    }
    if stripped.lower() in named:
        return datetime.now(timezone.utc) - named[stripped.lower()]

    # Try relative time first
    match = re.match(r"^(\d+)\s*([smhdwMy])$", stripped)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        deltas = {
            "s": timedelta(seconds=amount),
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
            "M": timedelta(days=amount * 30),
            "y": timedelta(days=amount * 365),
        }
        return datetime.now(timezone.utc) - deltas[unit]

    # Try ISO-8601 absolute date/datetime
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(stripped, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    raise ValueError(
        f"Invalid since value '{value}'. "
        "Use relative (30m, 2h, 1d) or ISO date (2026-02-14, 2026-02-14T10:00:00Z)"
    )


def parse_since_seconds(value: str) -> int:
    """Parse a relative time string like '12h', '2d' into total seconds.

    Raises ValueError on invalid input.
    """
    match = re.match(r"^(\d+)\s*([smhdwMy])$", value.strip())
    if not match:
        raise ValueError(f"Invalid time value '{value}'. Use e.g. 30s, 30m, 2h, 1d, 1w, 3M, 1y")
    amount, unit = int(match.group(1)), match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "M": 2592000, "y": 31536000}
    return amount * multipliers[unit]


def relative_time(dt: datetime) -> str:
    """Return a human-friendly relative time string like '2h ago'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - dt
    seconds = int(diff.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    weeks = days // 7
    return f"{weeks}w ago"
