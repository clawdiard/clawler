"""The Register source — snarky tech journalism via RSS (no key needed)."""
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# The Register section RSS feeds (all public)
REGISTER_FEEDS = [
    {"url": "https://www.theregister.com/headlines.atom", "section": "headlines"},
    {"url": "https://www.theregister.com/security/headlines.atom", "section": "security"},
    {"url": "https://www.theregister.com/software/headlines.atom", "section": "software"},
    {"url": "https://www.theregister.com/networks/headlines.atom", "section": "networks"},
    {"url": "https://www.theregister.com/data_centre/headlines.atom", "section": "data_centre"},
    {"url": "https://www.theregister.com/on_prem/headlines.atom", "section": "on_prem"},
    {"url": "https://www.theregister.com/offbeat/headlines.atom", "section": "offbeat"},
]

# Category mapping from section
_SECTION_CATEGORY = {
    "headlines": "tech",
    "security": "security",
    "software": "tech",
    "networks": "tech",
    "data_centre": "tech",
    "on_prem": "tech",
    "offbeat": "culture",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub("", text).strip()


def _parse_atom_date(date_str: str) -> Optional[datetime]:
    """Parse ISO 8601 / Atom date string."""
    if not date_str:
        return None
    try:
        # Try ISO 8601 first
        cleaned = date_str.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        pass
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None


class TheRegisterSource(BaseSource):
    """Crawl The Register via Atom feeds."""

    name = "theregister"

    def crawl(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: set = set()

        for feed_info in REGISTER_FEEDS:
            url = feed_info["url"]
            section = feed_info["section"]
            text = self.fetch_url(url)
            if not text:
                continue

            try:
                entries = self._parse_atom(text)
            except Exception as e:
                logger.warning(f"[theregister] Failed to parse {section} feed: {e}")
                continue

            for entry in entries:
                link = entry.get("link", "").strip()
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)

                title = _strip_html(entry.get("title", "")).strip()
                summary = _strip_html(entry.get("summary", "")).strip()
                if not title:
                    continue

                published = _parse_atom_date(entry.get("updated") or entry.get("published", ""))
                author = entry.get("author", "")

                articles.append(Article(
                    title=title,
                    url=link,
                    source="theregister",
                    summary=summary[:500] if summary else "",
                    timestamp=published,
                    author=author,
                    category=_SECTION_CATEGORY.get(section, "tech"),
                ))

        logger.info(f"[theregister] Collected {len(articles)} articles from {len(REGISTER_FEEDS)} feeds")
        return articles

    @staticmethod
    def _parse_atom(text: str) -> List[dict]:
        """Minimal Atom feed parser — no external deps."""
        entries = []
        # Split on <entry> tags
        parts = re.split(r"<entry[^>]*>", text)
        for part in parts[1:]:  # skip preamble
            end = part.find("</entry>")
            if end >= 0:
                part = part[:end]

            entry = {}
            # Title
            m = re.search(r"<title[^>]*>(.*?)</title>", part, re.DOTALL)
            if m:
                entry["title"] = _strip_html(m.group(1))

            # Link (href attribute)
            m = re.search(r'<link[^>]*href="([^"]+)"', part)
            if m:
                entry["link"] = m.group(1)

            # Summary/content
            for tag in ("summary", "content"):
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", part, re.DOTALL)
                if m:
                    entry["summary"] = _strip_html(m.group(1))
                    break

            # Updated/Published
            for tag in ("updated", "published"):
                m = re.search(rf"<{tag}>(.*?)</{tag}>", part)
                if m:
                    entry[tag] = m.group(1).strip()

            # Author
            m = re.search(r"<author>\s*<name>(.*?)</name>", part, re.DOTALL)
            if m:
                entry["author"] = m.group(1).strip()

            if entry.get("title") and entry.get("link"):
                entries.append(entry)

        return entries
