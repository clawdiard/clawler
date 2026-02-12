"""Feed autodiscovery — find RSS/Atom feed links on a webpage."""
import logging
import re
from typing import List, Dict
from bs4 import BeautifulSoup
from clawler.sources.base import BaseSource, HEADERS
import requests

logger = logging.getLogger(__name__)

# MIME types that indicate a feed
FEED_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/feed+json",
    "application/xml",
    "text/xml",
}


def discover_feeds(url: str, timeout: int = 15) -> List[Dict[str, str]]:
    """Discover RSS/Atom feeds linked from a webpage.

    Returns a list of dicts with 'url', 'title', and 'type' keys.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"[Discover] Failed to fetch {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    feeds: List[Dict[str, str]] = []
    seen_urls: set = set()

    # Method 1: <link> tags with rel="alternate" and feed MIME types
    for link in soup.find_all("link", rel="alternate"):
        href = link.get("href", "").strip()
        link_type = link.get("type", "").strip().lower()
        title = link.get("title", "").strip()

        if not href:
            continue
        if link_type and link_type not in FEED_TYPES:
            continue
        if not link_type and not any(kw in href.lower() for kw in ("rss", "feed", "atom", "xml")):
            continue

        # Resolve relative URLs
        if href.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"

        if href not in seen_urls:
            seen_urls.add(href)
            feeds.append({
                "url": href,
                "title": title or _guess_source(url),
                "type": link_type or "unknown",
            })

    # Method 2: Common feed URL patterns (fallback)
    if not feeds:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        common_paths = ["/feed", "/feed/", "/rss", "/rss.xml", "/atom.xml",
                        "/feeds/posts/default", "/index.xml", "/feed.xml"]
        for path in common_paths:
            candidate = base + path
            if candidate in seen_urls:
                continue
            try:
                r = requests.head(candidate, headers=HEADERS, timeout=5, allow_redirects=True)
                ct = r.headers.get("content-type", "").lower()
                if r.status_code == 200 and any(t in ct for t in ("xml", "rss", "atom", "feed")):
                    seen_urls.add(candidate)
                    feeds.append({
                        "url": candidate,
                        "title": _guess_source(url),
                        "type": ct.split(";")[0].strip(),
                    })
            except requests.RequestException:
                pass

    return feeds


def _guess_source(url: str) -> str:
    """Extract a reasonable source name from a URL."""
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    # Remove www. prefix and TLD
    host = re.sub(r"^www\.", "", host)
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2].capitalize()
    return host
