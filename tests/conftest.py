"""Shared test fixtures and configuration."""
import socket
import pytest


def _has_network():
    """Quick check for network availability."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False


# Mark for tests that require network access
requires_network = pytest.mark.skipif(
    not _has_network(),
    reason="No network access available",
)
