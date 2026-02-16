"""Wikipedia Current Events source — curated daily news from Wikipedia editors.

Parses the Wikipedia Current Events portal, which provides a human-curated
summary of notable world events updated daily.  Supports multi-day lookback
and the Main Page "In the news" section.  No API key required.
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

PORTAL_URL = "https://en.wikipedia.org/wiki/Portal:Current_events"
MAIN_PAGE_URL = "https://en.wikipedia.org/wiki/Main_Page"

# ── category mapping ──────────────────────────────────────────────────────────

_CATEGORY_KEYWORDS: Dict[str, tuple] = {
    "world": (
        "armed", "conflict", "attack", "war", "militar", "invasion",
        "politic", "election", "govern", "law", "legislat", "diplomacy",
        "treaty", "coup", "protest", "sanction", "refugee",
    ),
    "science": (
        "science", "space", "nasa", "launch", "orbit", "asteroid",
        "physics", "biology", "genome", "species", "fossil",
        "discover", "research", "study finds",
    ),
    "health": (
        "health", "medicine", "disease", "virus", "vaccine", "pandemic",
        "epidemi", "cancer", "fda", "who ", "outbreak", "hospital",
        "clinical", "drug approv", "therapy",
    ),
    "tech": (
        "technology", "software", "artificial intelligence", " ai ",
        "cyber", "data breach", "hack", "internet", "satellite",
        "quantum", "chip", "semiconductor", "robot",
    ),
    "business": (
        "business", "econom", "financ", "market", "trade", "inflation",
        "gdp", "stock", "bank", "merger", "acquisition", "ipo",
        "recession", "central bank", "tariff",
    ),
    "environment": (
        "environment", "climate", "weather", "earthquake", "flood",
        "hurricane", "wildfire", "typhoon", "tornado", "tsunami",
        "drought", "emission", "carbon", "disaster",
    ),
    "culture": (
        "sport", "football", "soccer", "olymp", "cricket", "tennis",
        "art", "film", "music", "award", "oscar", "grammy", "nobel",
        "death", "dies", "obit", "entertain",
    ),
}


def _map_category(text: str) -> str:
    """Map text to Clawler category using keyword matching with priority."""
    text_lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return "world"


# ── source ────────────────────────────────────────────────────────────────────


class WikipediaCurrentEventsSource(BaseSource):
    """Crawl curated events from Wikipedia's Current Events portal and Main Page.

    Features (v2):
    - Multi-day lookback via ``days`` parameter (fetches daily sub-pages)
    - Main Page "In the news" section via ``include_itn``
    - Granular category mapping (world, science, health, tech, business,
      environment, culture)
    - Section-type tags for provenance (``wiki:section:<heading>``)
    """

    name = "wikipedia"

    def __init__(
        self,
        days: int = 1,
        include_itn: bool = True,
        limit: int = 50,
    ):
        """
        Args:
            days: How many days of Current Events to fetch (1 = today only,
                  3 = today + 2 previous days). Max 7.
            include_itn: Also fetch the Main Page "In the news" box.
            limit: Maximum total articles to return.
        """
        self.days = min(max(days, 1), 7)
        self.include_itn = include_itn
        self.limit = limit

    def crawl(self) -> List[Article]:
        from bs4 import BeautifulSoup

        articles: List[Article] = []
        seen_urls: Set[str] = set()

        # ── Current Events portal (multi-day) ──
        if self.days == 1:
            # Single-day: use the main portal page (includes today)
            self._parse_portal_page(PORTAL_URL, articles, seen_urls)
        else:
            today = datetime.now(tz=timezone.utc).date()
            for i in range(self.days):
                day = today - timedelta(days=i)
                # Wikipedia daily sub-pages follow this pattern:
                url = (
                    f"https://en.wikipedia.org/wiki/Portal:Current_events/"
                    f"{day.strftime('%B')}_{day.day},_{day.year}"
                )
                self._parse_portal_page(url, articles, seen_urls, day_label=str(day))

        # ── Main Page "In the news" ──
        if self.include_itn:
            self._parse_itn(articles, seen_urls)

        # Enforce limit
        articles = articles[: self.limit]
        logger.info(
            f"[Wikipedia] Collected {len(articles)} events "
            f"({self.days}d portal{' + ITN' if self.include_itn else ''})"
        )
        return articles

    # ── portal parsing ────────────────────────────────────────────────────────

    def _parse_portal_page(
        self,
        url: str,
        articles: List[Article],
        seen_urls: Set[str],
        day_label: str = "today",
    ) -> None:
        from bs4 import BeautifulSoup

        html = self.fetch_url(url)
        if not html:
            logger.warning(f"[Wikipedia] Failed to fetch portal page: {url}")
            return

        soup = BeautifulSoup(html, "html.parser")

        # The portal content sits inside divs with class current-events-content
        # or role=region.  We try both.
        content_div = (
            soup.find("div", {"class": "current-events-content"})
            or soup.find("div", {"role": "region"})
            or soup
        )

        current_section = "general"
        for element in content_div.find_all(["b", "li", "p", "dl", "dt"]):
            # Detect section headings (bold text or <dt>)
            if element.name in ("b", "p", "dt"):
                heading_text = element.get_text(strip=True)
                if heading_text and len(heading_text) < 80:
                    current_section = heading_text
                continue

            if element.name != "li":
                continue

            text = element.get_text(" ", strip=True)
            if not text or len(text) < 20:
                continue

            # Extract the best URL from links
            links = element.find_all("a", href=True)
            ext_url, wiki_url = None, None
            for link in links:
                href = link["href"]
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/wiki/"):
                    href = "https://en.wikipedia.org" + href

                if "wikipedia.org" not in href and href.startswith("http"):
                    ext_url = ext_url or href
                elif "wikipedia.org" in href and "/wiki/" in href:
                    wiki_url = wiki_url or href

            url_choice = ext_url or wiki_url
            if not url_choice or url_choice in seen_urls:
                continue
            seen_urls.add(url_choice)

            title = text[:150].split(". ")[0].strip()
            if not title:
                continue

            category = _map_category(f"{current_section} {text}")

            tags = ["wikipedia", "curated", "current-events"]
            section_tag = re.sub(r"[^a-z0-9]+", "-", current_section.lower()).strip("-")
            if section_tag:
                tags.append(f"wiki:section:{section_tag}")
            if day_label != "today":
                tags.append(f"wiki:date:{day_label}")

            articles.append(
                Article(
                    title=title,
                    url=url_choice,
                    source="Wikipedia Current Events",
                    summary=text[:300] if len(text) > 150 else "",
                    timestamp=datetime.now(tz=timezone.utc),
                    category=category,
                    quality_score=0.80,
                    tags=tags,
                )
            )

    # ── Main Page "In the news" ───────────────────────────────────────────────

    def _parse_itn(self, articles: List[Article], seen_urls: Set[str]) -> None:
        """Parse the 'In the news' box from Wikipedia's Main Page."""
        from bs4 import BeautifulSoup

        html = self.fetch_url(MAIN_PAGE_URL)
        if not html:
            logger.warning("[Wikipedia] Failed to fetch Main Page for ITN")
            return

        soup = BeautifulSoup(html, "html.parser")

        # The ITN box has id="mp-itn" or is inside a div with that id
        itn_div = soup.find("div", {"id": "mp-itn"})
        if not itn_div:
            # Fallback: look for the heading text
            for h2 in soup.find_all("h2"):
                if "in the news" in h2.get_text().lower():
                    itn_div = h2.find_next("div")
                    break

        if not itn_div:
            logger.info("[Wikipedia] Could not locate ITN section on Main Page")
            return

        for li in itn_div.find_all("li"):
            text = li.get_text(" ", strip=True)
            if not text or len(text) < 15:
                continue

            # Find the bolded article link (Wikipedia convention: bold = main article)
            bold_link = li.find("b")
            main_url = None
            if bold_link:
                a_tag = bold_link.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    if href.startswith("/wiki/"):
                        main_url = "https://en.wikipedia.org" + href

            # Fallback to first link
            if not main_url:
                first_link = li.find("a", href=True)
                if first_link:
                    href = first_link["href"]
                    if href.startswith("/wiki/"):
                        main_url = "https://en.wikipedia.org" + href
                    elif href.startswith("http"):
                        main_url = href

            if not main_url or main_url in seen_urls:
                continue
            seen_urls.add(main_url)

            title = text[:150].split(". ")[0].strip()
            category = _map_category(text)

            articles.append(
                Article(
                    title=title,
                    url=main_url,
                    source="Wikipedia In the News",
                    summary=text[:300] if len(text) > 150 else "",
                    timestamp=datetime.now(tz=timezone.utc),
                    category=category,
                    quality_score=0.85,  # ITN items are highly notable
                    tags=["wikipedia", "curated", "in-the-news"],
                )
            )
