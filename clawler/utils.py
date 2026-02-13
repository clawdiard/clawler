"""Shared utility functions."""
import re
from datetime import datetime, timedelta, timezone


def parse_since(value: str) -> datetime:
    """Parse a relative time string like '1h', '30m', '2d' into a UTC datetime.

    Raises ValueError on invalid input.
    """
    match = re.match(r"^(\d+)\s*([smhdw])$", value.strip().lower())
    if not match:
        raise ValueError(f"Invalid since value '{value}'. Use e.g. 30s, 30m, 2h, 1d, 1w")
    amount, unit = int(match.group(1)), match.group(2)
    deltas = {
        "s": timedelta(seconds=amount),
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
        "w": timedelta(weeks=amount),
    }
    return datetime.now(timezone.utc) - deltas[unit]


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
