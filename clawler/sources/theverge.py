"""The Verge source — fetches articles from theverge.com RSS feeds.

Major tech news publication covering gadgets, science, entertainment,
and the intersection of technology and culture.

Enhanced with:
- Multiple section feeds (tech, science, entertainment, policy, creators)
- Keyword-based category detection with scoring
- Quality scoring based on author prominence and content signals
- Configurable section filtering
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from xml.etree import ElementTree

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Section feeds
VERGE_FEEDS: Dict[str, str] = {
    "all": "https://www.theverge.com/rss/index.xml",
    "tech": "https://www.theverge.com/rss/tech/index.xml",
    "science": "https://www.theverge.com/rss/science/index.xml",
    "entertainment": "https://www.theverge.com/rss/entertainment/index.xml",
    "policy": "https://www.theverge.com/rss/policy/index.xml",
    "creators": "https://www.theverge.com/rss/creators/index.xml",
}

# Prominent Verge authors (higher quality signal)
PROMINENT_AUTHORS = {
    "nilay patel", "dieter bohn", "david pierce", "alex cranz",
    "sean hollister", "chris welch", "tom warren", "james vincent",
    "adi robertson", "mitchell clark", "emma roth", "wes davis",
}

# Keyword categories with compiled regexes for scoring
_KEYWORD_CATEGORIES = {
    "ai": re.compile(r"\b(ai|artificial.intelligence|machine.?learn|llm|gpt|openai|anthropic|claude|gemini|chatgpt|copilot|diffusion|transformer|neural)\b", re.I),
    "security": re.compile(r"\b(security|hack|breach|privacy|surveillance|encrypt|vulnerabilit|malware|ransomware|zero.?day|exploit)\b", re.I),
    "science": re.compile(r"\b(science|space|nasa|climate|research|physics|biology|asteroid|rocket|mars|moon|quantum)\b", re.I),
    "gaming": re.compile(r"\b(game|gaming|playstation|xbox|nintendo|steam|valve|epic.games|esports|gpu|graphics.card)\b", re.I),
    "culture": re.compile(r"\b(movie|film|tv|streaming|netflix|disney|hbo|spotify|music|podcast|youtube|tiktok|social.media)\b", re.I),
    "business": re.compile(r"\b(acquisition|merger|layoff|ipo|funding|antitrust|lawsuit|ftc|regulation|monopoly)\b", re.I),
    "mobile": re.compile(r"\b(iphone|android|pixel|samsung|galaxy|smartphone|tablet|ipad|wearable|smartwatch)\b", re.I),
}


class TheVergeSource(BaseSource):
    """Fetch articles from The Verge's RSS feeds with quality scoring."""

    name = "theverge"

    def __init__(self, limit: int = 25, sections: Optional[List[str]] = None):
        """
        Args:
            limit: Max articles per feed.
            sections: Feed sections to crawl. Default: ["all"].
                      Options: all, tech, science, entertainment, policy, creators.
        """
        self.limit = limit
        self.sections = sections or ["all"]

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen: Set[str] = set()

        for section in self.sections:
            feed_url = VERGE_FEEDS.get(section, VERGE_FEEDS["all"])
            try:
                xml_text = self.fetch_url(feed_url)
                if not xml_text:
                    continue
                articles = self._parse_feed(xml_text, seen, section)
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[TheVerge] Failed to fetch {section} feed: {e}")

        logger.info(f"[TheVerge] Fetched {len(all_articles)} articles from {len(self.sections)} section(s)")
        return all_articles

    def _parse_feed(self, xml_text: str, seen: Set[str], section: str = "all") -> List[Article]:
        articles: List[Article] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"[TheVerge] XML parse error: {e}")
            return articles

        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # The Verge uses Atom format
        entries = root.findall("atom:entry", ns)
        if not entries:
            # Fallback to RSS 2.0
            entries = root.findall(".//item")

        for entry in entries[:self.limit]:
            try:
                article = self._parse_entry(entry, seen, ns, section)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[TheVerge] Skipping entry: {e}")

        return articles

    def _parse_entry(self, entry, seen: Set[str], ns: dict, section: str = "all") -> Optional[Article]:
        # Atom format
        title_el = entry.find("atom:title", ns)
        if title_el is None:
            title_el = entry.find("title")

        link_el = entry.find("atom:link[@rel='alternate']", ns)
        if link_el is not None:
            url = link_el.get("href", "").strip()
        else:
            link_el = entry.find("link")
            url = (link_el.text or "").strip() if link_el is not None else ""

        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title or not url:
            return None
        if url in seen:
            return None
        seen.add(url)

        # Summary / content
        summary = ""
        for tag in ["atom:summary", "atom:content"]:
            el = entry.find(tag, ns)
            if el is not None and el.text:
                summary = re.sub(r"<[^>]+>", "", el.text).strip()
                break
        if not summary:
            desc_el = entry.find("description")
            if desc_el is not None and desc_el.text:
                summary = re.sub(r"<[^>]+>", "", desc_el.text).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Author
        author = ""
        author_el = entry.find("atom:author/atom:name", ns)
        if author_el is not None and author_el.text:
            author = author_el.text.strip()

        # Timestamp
        ts = None
        for tag in ["atom:published", "atom:updated", "pubDate"]:
            ts_el = entry.find(tag, ns) if "atom:" in tag else entry.find(tag)
            if ts_el is not None and ts_el.text:
                ts = _parse_date(ts_el.text)
                if ts:
                    break

        # Categories / tags
        tags = []
        for cat_el in entry.findall("atom:category", ns):
            term = cat_el.get("term", "")
            if term:
                tags.append(f"verge:{term.strip().lower()}")
        for cat_el in entry.findall("category"):
            if cat_el.text:
                tags.append(f"verge:{cat_el.text.strip().lower()}")

        # Categorize based on tags/title
        category = _detect_category(title, tags)

        # Quality scoring
        quality = _compute_quality(title, summary, author, tags, section)

        # Section tag
        article_tags = tags.copy()
        if section != "all":
            article_tags.append(f"verge-section:{section}")

        return Article(
            title=title,
            url=url,
            source="The Verge" if section == "all" else f"The Verge ({section.title()})",
            summary=summary,
            timestamp=ts,
            category=category,
            tags=article_tags,
            author=author,
            quality_score=quality,
        )


def _detect_category(title: str, tags: List[str]) -> str:
    """Keyword-based category detection with priority scoring."""
    text = title.lower() + " " + " ".join(tags)
    best_cat = "tech"
    best_len = 0
    for cat, pattern in _KEYWORD_CATEGORIES.items():
        matches = pattern.findall(text)
        if matches and len(matches) > best_len:
            best_cat = cat
            best_len = len(matches)
    return best_cat


def _compute_quality(title: str, summary: str, author: str, tags: List[str], section: str) -> float:
    """Compute quality score (0.0–1.0) based on content signals."""
    score = 0.5  # baseline

    # Prominent author boost
    if author.lower() in PROMINENT_AUTHORS:
        score += 0.15

    # Title length signal (very short = low effort, very long = detailed)
    title_words = len(title.split())
    if title_words >= 6:
        score += 0.05
    if title_words >= 10:
        score += 0.05

    # Summary richness
    if len(summary) > 100:
        score += 0.05
    if len(summary) > 200:
        score += 0.05

    # Section-specific boosts (original reporting sections)
    if section in ("science", "policy"):
        score += 0.05

    # Keyword category match (specific > generic)
    text = f"{title} {summary}".lower()
    category_matches = sum(1 for _, pat in _KEYWORD_CATEGORIES.items() if pat.search(text))
    if category_matches >= 2:
        score += 0.05  # cross-category = broader significance

    return min(score, 1.0)


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    # ISO 8601
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        pass
    # RFC 2822
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(raw.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
