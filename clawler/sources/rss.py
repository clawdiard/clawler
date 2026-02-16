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
    # --- Tech (v4.4.0) ---
    {"url": "https://dev.to/feed", "source": "DEV Community", "category": "tech"},
    {"url": "https://rss.slashdot.org/Slashdot/slashdotMain", "source": "Slashdot", "category": "tech"},
    {"url": "https://www.theregister.com/headlines.atom", "source": "The Register", "category": "tech"},
    # --- Tech (v6.4.0) ---
    {"url": "https://www.freecodecamp.org/news/rss/", "source": "freeCodeCamp", "category": "tech"},
    {"url": "https://changelog.com/feed", "source": "The Changelog", "category": "tech"},
    {"url": "https://daringfireball.net/feeds/main", "source": "Daring Fireball", "category": "tech"},
    {"url": "https://www.anandtech.com/rss/", "source": "AnandTech", "category": "tech"},
    {"url": "https://this-week-in-rust.org/atom.xml", "source": "This Week in Rust", "category": "tech"},
    {"url": "https://blog.golang.org/feed.atom", "source": "Go Blog", "category": "tech"},
    # --- Finance ---
    {"url": "https://www.marketwatch.com/rss/topstories", "source": "MarketWatch", "category": "finance"},
    {"url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "source": "Yahoo Finance", "category": "finance"},
    {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk", "category": "finance"},
    # --- Health ---
    {"url": "https://www.statnews.com/feed/", "source": "STAT News", "category": "health"},
    {"url": "https://www.medicalnewstoday.com/newsrss.xml", "source": "Medical News Today", "category": "health"},
    # --- Sports ---
    {"url": "https://www.espn.com/espn/rss/news", "source": "ESPN", "category": "sports"},
    {"url": "https://theathletic.com/rss/news/", "source": "The Athletic", "category": "sports"},
    # --- Gaming ---
    {"url": "https://kotaku.com/rss", "source": "Kotaku", "category": "gaming"},
    {"url": "https://www.polygon.com/rss/index.xml", "source": "Polygon", "category": "gaming"},
    {"url": "https://www.rockpapershotgun.com/feed", "source": "Rock Paper Shotgun", "category": "gaming"},
    # --- Design ---
    {"url": "https://feeds.feedburner.com/SmashingMagazine", "source": "Smashing Magazine", "category": "design"},
    {"url": "https://alistapart.com/main/feed/", "source": "A List Apart", "category": "design"},
    # --- Music ---
    {"url": "https://pitchfork.com/feed/feed-news/rss", "source": "Pitchfork", "category": "music"},
    {"url": "https://www.stereogum.com/feed/", "source": "Stereogum", "category": "music"},
    # --- Food ---
    {"url": "https://www.seriouseats.com/feeds/serious-eats", "source": "Serious Eats", "category": "food"},
    {"url": "https://www.eater.com/rss/index.xml", "source": "Eater", "category": "food"},
    # --- Travel ---
    {"url": "https://www.lonelyplanet.com/news/feed", "source": "Lonely Planet", "category": "travel"},
    {"url": "https://feeds.feedburner.com/MatadorNetwork", "source": "Matador Network", "category": "travel"},
    # --- International ---
    {"url": "https://www.france24.com/en/rss", "source": "France24", "category": "world"},
    {"url": "https://www3.nhk.or.jp/nhkworld/en/news/feeds/", "source": "NHK World", "category": "world"},
    {"url": "https://www.scmp.com/rss/91/feed", "source": "South China Morning Post", "category": "world"},
    # --- Space ---
    {"url": "https://www.space.com/feeds/all", "source": "Space.com", "category": "science"},
    {"url": "https://spacenews.com/feed/", "source": "SpaceNews", "category": "science"},
    {"url": "https://www.nasaspaceflight.com/feed/", "source": "NASASpaceFlight", "category": "science"},
    # --- Environment & Climate ---
    {"url": "https://grist.org/feed/", "source": "Grist", "category": "environment"},
    {"url": "https://www.carbonbrief.org/feed/", "source": "Carbon Brief", "category": "environment"},
    {"url": "https://insideclimatenews.org/feed/", "source": "Inside Climate News", "category": "environment"},
    # --- Education ---
    {"url": "https://www.edsurge.com/articles_rss", "source": "EdSurge", "category": "education"},
    {"url": "https://theconversation.com/us/articles.atom", "source": "The Conversation US", "category": "education"},
    # --- Law & Policy ---
    {"url": "https://www.lawfaremedia.org/feed", "source": "Lawfare", "category": "policy"},
    {"url": "https://www.scotusblog.com/feed/", "source": "SCOTUSblog", "category": "policy"},
    # --- Automotive & EV ---
    {"url": "https://electrek.co/feed/", "source": "Electrek", "category": "automotive"},
    {"url": "https://insideevs.com/rss/news/", "source": "InsideEVs", "category": "automotive"},
    # --- Real Estate ---
    {"url": "https://www.curbed.com/rss/index.xml", "source": "Curbed", "category": "realestate"},
    # --- Lifestyle ---
    {"url": "https://lifehacker.com/rss", "source": "Lifehacker", "category": "lifestyle"},
    # --- Startups & VC ---
    {"url": "https://news.crunchbase.com/feed/", "source": "Crunchbase News", "category": "business"},
    {"url": "https://sifted.eu/feed", "source": "Sifted (EU Startups)", "category": "business"},
    # --- International (more) ---
    {"url": "https://www.abc.net.au/news/feed/2942460/rss.xml", "source": "ABC Australia", "category": "world"},
    {"url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "source": "Times of India", "category": "world"},
    {"url": "https://www.jpost.com/rss/rssfeedsfrontpage.aspx", "source": "Jerusalem Post", "category": "world"},
    # --- Health (expanded) ---
    {"url": "https://www.who.int/feeds/entity/mediacentre/news/en/rss.xml", "source": "WHO News", "category": "health"},
    {"url": "https://www.healthline.com/rss", "source": "Healthline", "category": "health"},
    {"url": "https://www.psychologytoday.com/us/blog/feed", "source": "Psychology Today", "category": "health"},
    # --- Sports (expanded) ---
    {"url": "https://www.bbc.co.uk/sport/rss.xml", "source": "BBC Sport", "category": "sports"},
    {"url": "https://www.si.com/.rss/full/", "source": "Sports Illustrated", "category": "sports"},
    # --- Design (expanded) ---
    {"url": "https://www.designweek.co.uk/feed/", "source": "Design Week", "category": "design"},
    {"url": "https://uxdesign.cc/feed", "source": "UX Collective", "category": "design"},
    {"url": "https://css-tricks.com/feed/", "source": "CSS-Tricks", "category": "design"},
    # --- Music (expanded) ---
    {"url": "https://consequenceofsound.net/feed/", "source": "Consequence of Sound", "category": "music"},
    {"url": "https://www.nme.com/feed", "source": "NME", "category": "music"},
    # --- Food (expanded) ---
    {"url": "https://www.bonappetit.com/feed/rss", "source": "Bon Appetit", "category": "food"},
    {"url": "https://www.foodandwine.com/feeds/all", "source": "Food & Wine", "category": "food"},
    # --- Photography & Art ---
    {"url": "https://petapixel.com/feed/", "source": "PetaPixel", "category": "photography"},
    {"url": "https://www.thisiscolossal.com/feed/", "source": "Colossal", "category": "art"},
    # --- Economics & Markets ---
    {"url": "https://www.economist.com/finance-and-economics/rss.xml", "source": "The Economist (Finance)", "category": "finance"},
    {"url": "https://www.ft.com/rss/home", "source": "Financial Times", "category": "finance"},
    # --- Parenting & Family ---
    {"url": "https://www.todaysparent.com/feed/", "source": "Today's Parent", "category": "family"},
    # --- Architecture ---
    {"url": "https://www.dezeen.com/feed/", "source": "Dezeen", "category": "architecture"},
    {"url": "https://www.archdaily.com/feed", "source": "ArchDaily", "category": "architecture"},
    # --- History ---
    {"url": "https://www.smithsonianmag.com/rss/history/", "source": "Smithsonian History", "category": "history"},
    # Expansion 2026-02-16: 20 feeds in underrepresented + new categories
    # Outdoors & Adventure
    {"url": "https://www.outsideonline.com/feed/", "source": "Outside Magazine", "category": "outdoors"},
    {"url": "https://www.adventure-journal.com/feed/", "source": "Adventure Journal", "category": "outdoors"},
    {"url": "https://gearjunkie.com/feed", "source": "GearJunkie", "category": "outdoors"},
    # Culture & Society
    {"url": "https://www.newyorker.com/feed/culture", "source": "The New Yorker Culture", "category": "culture"},
    {"url": "https://www.theatlantic.com/feed/channel/culture/", "source": "The Atlantic Culture", "category": "culture"},
    # Parenting & Family
    {"url": "https://www.fatherly.com/rss", "source": "Fatherly", "category": "family"},
    # Personal Finance
    {"url": "https://www.nerdwallet.com/blog/feed/", "source": "NerdWallet", "category": "finance"},
    {"url": "https://feeds.feedburner.com/MrMoneyMustache", "source": "Mr Money Mustache", "category": "finance"},
    # Investigative / Longform
    {"url": "https://theintercept.com/feed/?rss", "source": "The Intercept", "category": "investigative"},
    {"url": "https://www.propublica.org/feeds/propublica/main", "source": "ProPublica", "category": "investigative"},
    # Real Estate & Housing
    {"url": "https://therealdeal.com/feed/", "source": "The Real Deal", "category": "realestate"},
    # Philosophy & Ideas
    {"url": "https://aeon.co/feed.rss", "source": "Aeon", "category": "philosophy"},
    {"url": "https://dailynous.com/feed/", "source": "Daily Nous", "category": "philosophy"},
    # Fitness & Wellness
    {"url": "https://www.menshealth.com/rss/all.xml/", "source": "Mens Health", "category": "fitness"},
    {"url": "https://www.runnersworld.com/rss/all.xml/", "source": "Runners World", "category": "fitness"},
    # Podcasts & Audio
    {"url": "https://podnews.net/rss", "source": "Podnews", "category": "media"},
    # Retail & E-Commerce
    {"url": "https://www.modernretail.co/feed/", "source": "Modern Retail", "category": "business"},
    # Aviation & Transport
    {"url": "https://simpleflying.com/feed/", "source": "Simple Flying", "category": "aviation"},
    # Comics & Animation
    {"url": "https://www.cartoonbrew.com/feed", "source": "Cartoon Brew", "category": "animation"},
    # Skateboarding
    {"url": "https://www.thrashermagazine.com/rss/", "source": "Thrasher", "category": "sports"},
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
                # Fetch through base class for rate limiting + retries
                raw = self.fetch_url(url)
                if not raw:
                    logger.warning(f"[RSS] Empty response from {source}")
                    continue
                d = feedparser.parse(raw)
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
