"""RSS/Atom feed source — the workhorse of Clawler."""
import logging
from datetime import datetime
from typing import List, Optional
import feedparser
from dateutil import parser as dateparser
from clawler.models import Article
from clawler.sources.base import BaseSource, HEADERS

logger = logging.getLogger(__name__)

# Curated list of high-quality RSS feeds
DEFAULT_FEEDS = [
    # --- Tech ---
    {"url": "https://feeds.arstechnica.com/arstechnica/index", "source": "Ars Technica", "category": "tech"},
    {"url": "https://www.theverge.com/rss/index.xml", "source": "The Verge", "category": "tech"},
    {"url": "https://techcrunch.com/feed/", "source": "TechCrunch", "category": "tech"},
    {"url": "https://www.wired.com/feed/rss", "source": "Wired", "category": "tech"},
    {"url": "https://feeds.feedburner.com/TheHackersNews", "source": "The Hacker News", "category": "tech"},
    # --- World News ---
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "source": "NY Times", "category": "world"},
    {"url": "https://feeds.bbci.co.uk/news/rss.xml", "source": "BBC News", "category": "world"},
    {"url": "https://www.theguardian.com/world/rss", "source": "The Guardian", "category": "world"},
    {"url": "http://feeds.reuters.com/reuters/topNews", "source": "Reuters", "category": "world"},
    {"url": "https://rss.cnn.com/rss/edition.rss", "source": "CNN", "category": "world"},
    # --- Science ---
    {"url": "https://www.sciencedaily.com/rss/all.xml", "source": "ScienceDaily", "category": "science"},
    {"url": "https://phys.org/rss-feed/", "source": "Phys.org", "category": "science"},
    # --- Business ---
    {"url": "https://feeds.bloomberg.com/markets/news.rss", "source": "Bloomberg", "category": "business"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "source": "CNBC", "category": "business"},
    # --- Tech (expanded) ---
    {"url": "https://www.technologyreview.com/feed/", "source": "MIT Technology Review", "category": "tech"},
    {"url": "https://spectrum.ieee.org/feeds/feed.rss", "source": "IEEE Spectrum", "category": "tech"},
    {"url": "https://lwn.net/headlines/rss", "source": "LWN.net", "category": "tech"},
    {"url": "https://lobste.rs/rss", "source": "Lobsters", "category": "tech"},
    {"url": "https://www.phoronix.com/rss.php", "source": "Phoronix", "category": "tech"},
    {"url": "https://www.404media.co/rss/", "source": "404 Media", "category": "tech"},
    {"url": "https://www.techdirt.com/feed/", "source": "TechDirt", "category": "tech"},
    {"url": "https://thenextweb.com/feed", "source": "The Next Web", "category": "tech"},
    {"url": "https://torrentfreak.com/feed/", "source": "TorrentFreak", "category": "tech"},
    {"url": "https://restofworld.org/feed/", "source": "Rest of World", "category": "tech"},
    {"url": "https://hnrss.org/show", "source": "HN Show", "category": "tech"},
    {"url": "https://hnrss.org/ask", "source": "HN Ask", "category": "tech"},
    # --- Security ---
    {"url": "https://www.schneier.com/feed/", "source": "Schneier on Security", "category": "security"},
    {"url": "https://krebsonsecurity.com/feed/", "source": "Krebs on Security", "category": "security"},
    {"url": "https://www.eff.org/rss/updates.xml", "source": "EFF Updates", "category": "security"},
    # --- World News (expanded) ---
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "source": "Al Jazeera", "category": "world"},
    {"url": "https://rss.dw.com/rdf/rss-en-all", "source": "DW", "category": "world"},
    {"url": "https://feeds.npr.org/1001/rss.xml", "source": "NPR", "category": "world"},
    # --- Science (expanded) ---
    {"url": "https://www.nature.com/nature.rss", "source": "Nature", "category": "science"},
    {"url": "https://theconversation.com/articles.atom", "source": "The Conversation", "category": "science"},
    {"url": "https://www.newscientist.com/feed/home", "source": "New Scientist", "category": "science"},
    {"url": "https://nautil.us/feed/", "source": "Nautilus", "category": "science"},
    # --- Investigative ---
    {"url": "https://www.propublica.org/feeds/propublica/main", "source": "ProPublica", "category": "investigative"},
    {"url": "https://theintercept.com/feed/?rss", "source": "The Intercept", "category": "investigative"},
    # --- Culture ---
    {"url": "https://www.theatlantic.com/feed/all/", "source": "The Atlantic", "category": "culture"},
    # --- Science (academic) ---
    {"url": "http://rss.arxiv.org/rss/cs.AI", "source": "ArXiv CS.AI", "category": "science"},
    {"url": "http://rss.arxiv.org/rss/cs.LG", "source": "ArXiv CS.LG", "category": "science"},
    # --- Tech (additional) ---
    {"url": "https://hnrss.org/best", "source": "HN Best", "category": "tech"},
    {"url": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss", "source": "IEEE AI", "category": "tech"},
    # --- Aggregator ---
    {"url": "https://news.google.com/rss", "source": "Google News", "category": "world"},
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB", "source": "Google News (Tech)", "category": "tech"},
]


class RSSSource(BaseSource):
    """Crawl multiple RSS/Atom feeds."""

    name = "rss"

    def __init__(self, feeds: Optional[List[dict]] = None):
        self.feeds = feeds or DEFAULT_FEEDS

    def _parse_date(self, entry) -> Optional[datetime]:
        for field in ("published", "updated", "created"):
            val = getattr(entry, field, None)
            if val:
                try:
                    return dateparser.parse(val)
                except (ValueError, TypeError):
                    pass
        struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if struct:
            try:
                return datetime(*struct[:6])
            except Exception:
                pass
        return None

    def _get_summary(self, entry) -> str:
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        # Strip HTML tags simply
        from bs4 import BeautifulSoup
        text = BeautifulSoup(summary, "html.parser").get_text(separator=" ", strip=True)
        return text[:300] + "..." if len(text) > 300 else text

    def crawl(self) -> List[Article]:
        articles = []
        for feed_cfg in self.feeds:
            url = feed_cfg["url"]
            source = feed_cfg.get("source", url)
            category = feed_cfg.get("category", "general")
            try:
                d = feedparser.parse(url, agent=HEADERS["User-Agent"])
                for entry in d.entries[:20]:  # cap per feed
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    if not title or not link:
                        continue
                    articles.append(Article(
                        title=title,
                        url=link,
                        source=source,
                        summary=self._get_summary(entry),
                        timestamp=self._parse_date(entry),
                        category=category,
                    ))
                logger.info(f"[RSS] {source}: {len(d.entries)} entries")
            except Exception as e:
                logger.warning(f"[RSS] Failed {source}: {e}")
        return articles
