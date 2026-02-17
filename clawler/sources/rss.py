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
    # Books & Literature
    {"url": "https://lithub.com/feed/", "source": "Literary Hub", "category": "books"},
    {"url": "https://www.theguardian.com/books/rss", "source": "The Guardian Books", "category": "books"},
    {"url": "https://bookmarks.reviews/feed/", "source": "Bookmarks Reviews", "category": "books"},
    # History (expanding)
    {"url": "https://www.historytoday.com/feed/rss.xml", "source": "History Today", "category": "history"},
    {"url": "https://theconversation.com/us/arts/history/articles.atom", "source": "The Conversation History", "category": "history"},
    # Art (expanding)
    {"url": "https://hyperallergic.com/feed/", "source": "Hyperallergic", "category": "art"},
    {"url": "https://www.artnews.com/feed/", "source": "ARTnews", "category": "art"},
    # Photography (expanding)
    {"url": "https://www.dpreview.com/feeds/news.xml", "source": "DPReview", "category": "photography"},
    {"url": "https://fstoppers.com/rss.xml", "source": "Fstoppers", "category": "photography"},
    # Energy
    {"url": "https://www.utilitydive.com/feeds/news/", "source": "Utility Dive", "category": "energy"},
    {"url": "https://cleantechnica.com/feed/", "source": "CleanTechnica", "category": "energy"},
    {"url": "https://www.greentechmedia.com/feed", "source": "GreenTech Media", "category": "energy"},
    # Parenting & Family (expanding)
    {"url": "https://www.fatherly.com/feed", "source": "Fatherly RSS", "category": "family"},
    {"url": "https://www.parents.com/feed/", "source": "Parents Magazine", "category": "family"},
    # Media & Journalism (expanding)
    {"url": "https://www.niemanlab.org/feed/", "source": "Nieman Lab", "category": "media"},
    {"url": "https://pressgazette.co.uk/feed/", "source": "Press Gazette", "category": "media"},
    # Lifestyle (expanding)
    {"url": "https://www.refinery29.com/en-us/feed.xml", "source": "Refinery29", "category": "lifestyle"},
    {"url": "https://www.vox.com/rss/index.xml", "source": "Vox", "category": "culture"},
    # Podcasting & Audio
    {"url": "https://hotpodnews.com/feed/", "source": "Hot Pod News", "category": "media"},
    # Fashion
    {"url": "https://www.businessoffashion.com/feed", "source": "Business of Fashion", "category": "fashion"},
    {"url": "https://fashionista.com/.rss/full/", "source": "Fashionista", "category": "fashion"},
    {"url": "https://www.highsnobiety.com/feed/", "source": "Highsnobiety", "category": "fashion"},
    # Parenting & Education (expanding)
    {"url": "https://www.teachertoolkit.co.uk/feed/", "source": "TeacherToolkit", "category": "education"},
    {"url": "https://www.insidehighered.com/rss/news", "source": "Inside Higher Ed", "category": "education"},
    # Travel (expanding)
    {"url": "https://www.atlasobscura.com/feeds/latest", "source": "Atlas Obscura", "category": "travel"},
    {"url": "https://www.afar.com/feed", "source": "AFAR", "category": "travel"},
    # Fitness (expanding)
    {"url": "https://www.womenshealthmag.com/rss/all.xml/", "source": "Women's Health", "category": "fitness"},
    {"url": "https://breakingmuscle.com/feed/", "source": "Breaking Muscle", "category": "fitness"},
    # Aviation (expanding)
    {"url": "https://thepointsguy.com/feed/", "source": "The Points Guy", "category": "aviation"},
    {"url": "https://www.avweb.com/feed/", "source": "AVweb", "category": "aviation"},
    # Automotive (expanding)
    {"url": "https://www.thedrive.com/feed", "source": "The Drive", "category": "automotive"},
    # Architecture (expanding)
    {"url": "https://www.designboom.com/feed/", "source": "Designboom", "category": "architecture"},
    # DIY & Maker (new category)
    {"url": "https://makezine.com/feed/", "source": "Make Magazine", "category": "maker"},
    {"url": "https://hackaday.com/feed/", "source": "Hackaday", "category": "maker"},
    {"url": "https://www.instructables.com/feed/", "source": "Instructables", "category": "maker"},
    # Pets & Animals (new category)
    {"url": "https://www.akc.org/feed/", "source": "AKC", "category": "pets"},
    {"url": "https://www.thedodo.com/rss", "source": "The Dodo", "category": "pets"},
    {"url": "https://www.catster.com/feed/", "source": "Catster", "category": "pets"},
    # Animation & VFX (expanding)
    {"url": "https://www.awn.com/rss.xml", "source": "Animation World Network", "category": "animation"},
    {"url": "https://animationmagazine.net/feed/", "source": "Animation Magazine", "category": "animation"},
    # Policy & Governance (expanding)
    {"url": "https://www.brookings.edu/feed/", "source": "Brookings Institution", "category": "policy"},
    {"url": "https://www.cfr.org/rss", "source": "Council on Foreign Relations", "category": "policy"},
    # Real Estate (expanding)
    {"url": "https://www.bisnow.com/feed", "source": "Bisnow", "category": "realestate"},
    # Lifestyle (expanding)
    {"url": "https://www.apartmenttherapy.com/feed.xml", "source": "Apartment Therapy", "category": "lifestyle"},
    {"url": "https://www.manrepeller.com/feed", "source": "Man Repeller", "category": "lifestyle"},
    # Philosophy (expanding)
    {"url": "https://blog.apaonline.org/feed/", "source": "APA Blog", "category": "philosophy"},
    # Weather & Meteorology (new category)
    {"url": "https://www.severe-weather.eu/feed/", "source": "Severe Weather Europe", "category": "weather"},
    {"url": "https://yaleclimateconnections.org/feed/", "source": "Yale Climate Connections", "category": "weather"},
    {"url": "https://www.washingtonpost.com/blogs/capital-weather-gang/feed/", "source": "Capital Weather Gang", "category": "weather"},
    # Linguistics & Language (new category)
    {"url": "https://languagelog.ldc.upenn.edu/nll/?feed=rss2", "source": "Language Log", "category": "linguistics"},
    {"url": "https://blog.duolingo.com/feed/", "source": "Duolingo Blog", "category": "linguistics"},
    # Cybersecurity (expanding security)
    {"url": "https://www.darkreading.com/rss.xml", "source": "Dark Reading", "category": "security"},
    {"url": "https://feeds.feedburner.com/TheHackersNews", "source": "The Hacker News", "category": "security"},
    # Gaming (expanding)
    {"url": "https://www.gamesindustry.biz/feed", "source": "GamesIndustry.biz", "category": "gaming"},
    {"url": "https://www.pcgamer.com/rss/", "source": "PC Gamer", "category": "gaming"},
    # Linguistics (expanding 2→4)
    {"url": "https://languagelog.ldc.upenn.edu/nll/?feed=rss2", "source": "Language Log", "category": "linguistics"},
    {"url": "https://blog.oup.com/category/languages-linguistics/feed/", "source": "OUP Linguistics", "category": "linguistics"},
    # Environment (expanding 3→5)
    {"url": "https://www.treehugger.com/feeds/all", "source": "Treehugger", "category": "environment"},
    {"url": "https://e360.yale.edu/feed", "source": "Yale E360", "category": "environment"},
    # Photography (expanding 3→5)
    {"url": "https://www.thephoblographer.com/feed/", "source": "The Phoblographer", "category": "photography"},
    {"url": "https://www.imaging-resource.com/news/feed", "source": "Imaging Resource", "category": "photography"},
    # Outdoors (expanding 3→5)
    {"url": "https://www.backpacker.com/feed/", "source": "Backpacker", "category": "outdoors"},
    {"url": "https://www.trailrunnermag.com/feed/", "source": "Trail Runner", "category": "outdoors"},
    # Philosophy (expanding 3→5)
    {"url": "https://dailystoic.com/feed/", "source": "Daily Stoic", "category": "philosophy"},
    {"url": "https://philosophynow.org/rss", "source": "Philosophy Now", "category": "philosophy"},
    # Math & Statistics (NEW)
    {"url": "https://www.quantamagazine.org/feed/", "source": "Quanta Magazine", "category": "math"},
    {"url": "https://mathblog.com/feed/", "source": "Math Blog", "category": "math"},
    {"url": "https://www.johndcook.com/blog/feed/", "source": "John D. Cook", "category": "math"},
    # Labor & Workplace (NEW)
    {"url": "https://www.worklife.news/feed/", "source": "WorkLife", "category": "workplace"},
    {"url": "https://www.hrdive.com/feeds/news/", "source": "HR Dive", "category": "workplace"},
    {"url": "https://www.personneltoday.com/feed/", "source": "Personnel Today", "category": "workplace"},
    # Podcasting & Audio (NEW)
    {"url": "https://podnews.net/rss", "source": "Podnews", "category": "audio"},
    {"url": "https://www.theverge.com/rss/podcasts/index.xml", "source": "Verge Podcasts", "category": "audio"},
    # Audio (expand 2→5)
    {"url": "https://www.audiokinetic.com/feed/", "source": "Audiokinetic", "category": "audio"},
    {"url": "https://www.soundonsound.com/feed/all", "source": "Sound On Sound", "category": "audio"},
    {"url": "https://audiophilestyle.com/rss/1-audiophile-style/", "source": "Audiophile Style", "category": "audio"},
    # Automotive (expand 3→5)
    {"url": "https://www.motortrend.com/feed/", "source": "MotorTrend", "category": "automotive"},
    {"url": "https://www.caranddriver.com/rss/all.xml/", "source": "Car and Driver", "category": "automotive"},
    # Real Estate (expand 3→5)
    {"url": "https://www.inman.com/feed/", "source": "Inman", "category": "realestate"},
    {"url": "https://www.housingwire.com/feed/", "source": "HousingWire", "category": "realestate"},
    # Art (expand 3→5)
    {"url": "https://www.artsy.net/rss/news", "source": "Artsy", "category": "art"},
    {"url": "https://www.juxtapoz.com/feed/", "source": "Juxtapoz", "category": "art"},
    # Architecture (expand 3→5)
    {"url": "https://www.architecturaldigest.com/feed/rss", "source": "Architectural Digest", "category": "architecture"},
    {"url": "https://www.curbed.com/rss/architecture/index.xml", "source": "Curbed Architecture", "category": "architecture"},
    # History (expand 3→5)
    {"url": "https://www.historyextra.com/feed/", "source": "HistoryExtra", "category": "history"},
    {"url": "https://www.ancient-origins.net/rss", "source": "Ancient Origins", "category": "history"},
    # Aviation (expand 3→5)
    {"url": "https://www.flyingmag.com/feed/", "source": "Flying Magazine", "category": "aviation"},
    {"url": "https://www.aerotime.aero/feed", "source": "AeroTime Hub", "category": "aviation"},
    # Animation (expand 3→5)
    {"url": "https://www.animationworld.net/rss.xml", "source": "Animation World Network", "category": "animation"},
    {"url": "https://motionographer.com/feed/", "source": "Motionographer", "category": "animation"},
    # Books (expand 3→5)
    {"url": "https://www.tor.com/feed/", "source": "Tor.com", "category": "books"},
    {"url": "https://bookriot.com/feed/", "source": "Book Riot", "category": "books"},
    # Energy (expand 3→5)
    {"url": "https://www.energymonitor.ai/feed/", "source": "Energy Monitor", "category": "energy"},
    {"url": "https://reneweconomy.com.au/feed/", "source": "RenewEconomy", "category": "energy"},
    # Fashion (expand 3→5)
    {"url": "https://www.whowhatwear.com/rss", "source": "Who What Wear", "category": "fashion"},
    {"url": "https://www.refinery29.com/fashion/rss.xml", "source": "Refinery29 Fashion", "category": "fashion"},
    # Maker (expand 3→5)
    {"url": "https://blog.adafruit.com/feed/", "source": "Adafruit", "category": "maker"},
    {"url": "https://makezine.com/feed/", "source": "Make Magazine Blog", "category": "maker"},
    # Pets (expand 3→5)
    {"url": "https://www.petmd.com/rss.xml", "source": "PetMD", "category": "pets"},
    {"url": "https://www.catster.com/feed/", "source": "Catster", "category": "pets"},
    # Weather (expand 3→5)
    {"url": "https://www.severe-weather.eu/feed/", "source": "Severe Weather Europe", "category": "weather"},
    {"url": "https://yaleclimateconnections.org/feed/", "source": "Yale Climate Connections", "category": "weather"},
    # Math (expand 3→5)
    {"url": "https://www.mathsisfun.com/news/feed/", "source": "Math Is Fun", "category": "math"},
    {"url": "https://blogs.ams.org/mathgradblog/feed/", "source": "AMS Grad Blog", "category": "math"},
    # Workplace (expand 3→5)
    {"url": "https://www.shrm.org/rss/pages/custom-rss-feeds.aspx", "source": "SHRM", "category": "workplace"},
    {"url": "https://www.ere.net/feed/", "source": "ERE", "category": "workplace"},
    # Parenting & Childcare (NEW)
    {"url": "https://www.scarymommy.com/feed", "source": "Scary Mommy", "category": "parenting"},
    {"url": "https://raisingchildren.net.au/rss", "source": "Raising Children", "category": "parenting"},
    {"url": "https://www.mother.ly/feed/", "source": "Motherly", "category": "parenting"},
    # Gardening (NEW)
    {"url": "https://www.gardeningknowhow.com/feed", "source": "Gardening Know How", "category": "gardening"},
    {"url": "https://savvygardening.com/feed/", "source": "Savvy Gardening", "category": "gardening"},
    {"url": "https://awaytogarden.com/feed/", "source": "A Way to Garden", "category": "gardening"},
    # Parenting (expanding 3→5)
    {"url": "https://www.parents.com/syndication/rss/", "source": "Parents", "category": "parenting"},
    {"url": "https://www.fatherly.com/rss", "source": "Fatherly Parenting", "category": "parenting"},
    # Gardening (expanding 3→5)
    {"url": "https://www.finegardening.com/feed", "source": "Fine Gardening", "category": "gardening"},
    {"url": "https://empressofdirt.net/feed/", "source": "Empress of Dirt", "category": "gardening"},
    # Investigative (expanding 4→5)
    {"url": "https://www.revealnews.org/feed/", "source": "Reveal", "category": "investigative"},
    # Culture (expanding 4→5)
    {"url": "https://hyperallergic.com/feed/", "source": "Hyperallergic Culture", "category": "culture"},
    # Music (expanding 4→5)
    {"url": "https://www.musicradar.com/rss", "source": "MusicRadar", "category": "music"},
    # Food (expanding 4→5)
    {"url": "https://www.bonappetit.com/feed/rss", "source": "Bon Appetit Extra", "category": "food"},
    # Travel (expanding 4→5)
    {"url": "https://www.cntraveler.com/feed/rss", "source": "Condé Nast Traveler", "category": "travel"},
    # Education (expanding 4→5)
    {"url": "https://www.edsurge.com/feeds/articles", "source": "EdSurge Extra", "category": "education"},
    # Policy (expanding 4→5)
    {"url": "https://www.brennancenter.org/rss", "source": "Brennan Center", "category": "policy"},
    # Lifestyle (expanding 4→5)
    {"url": "https://www.apartmenttherapy.com/main.rss", "source": "Apartment Therapy", "category": "lifestyle"},
    # Family (expanding 4→5)
    {"url": "https://www.todaysparent.com/feed/", "source": "Today's Parent Extra", "category": "family"},
    # Fitness (expanding 4→5)
    {"url": "https://www.self.com/feed/rss", "source": "Self", "category": "fitness"},
    # Media (expanding 4→5)
    {"url": "https://www.cjr.org/feed", "source": "Columbia Journalism Review", "category": "media"},
    # Linguistics (expanding 4→5)
    {"url": "https://www.ethnologue.com/feed", "source": "Ethnologue", "category": "linguistics"},
    # Military & Defense (NEW)
    {"url": "https://www.defensenews.com/arc/outboundfeeds/rss/", "source": "Defense News", "category": "military"},
    {"url": "https://www.thedrive.com/the-war-zone/rss", "source": "The War Zone", "category": "military"},
    {"url": "https://breakingdefense.com/feed/", "source": "Breaking Defense", "category": "military"},
    # Military (expanding 3→5)
    {"url": "https://www.military.com/daily-news/headlines/feed", "source": "Military.com", "category": "military"},
    {"url": "https://www.janes.com/feeds/news", "source": "Janes", "category": "military"},
    # Robotics (NEW)
    {"url": "https://spectrum.ieee.org/feeds/topic/robotics.rss", "source": "IEEE Robotics", "category": "robotics"},
    {"url": "https://www.therobotreport.com/feed/", "source": "The Robot Report", "category": "robotics"},
    {"url": "https://robohub.org/feed/", "source": "Robohub", "category": "robotics"},
    # Robotics (expanding 3→5)
    {"url": "https://www.automate.org/rss/blogs", "source": "Automate", "category": "robotics"},
    {"url": "https://roboticsandautomationnews.com/feed/", "source": "Robotics & Automation News", "category": "robotics"},
    # Marine & Oceans (NEW)
    {"url": "https://oceanservice.noaa.gov/rss/news.xml", "source": "NOAA Ocean Service", "category": "marine"},
    {"url": "https://www.whoi.edu/feed/", "source": "Woods Hole Oceanographic", "category": "marine"},
    {"url": "https://www.maritime-executive.com/feed", "source": "Maritime Executive", "category": "marine"},
    {"url": "https://www.oceannews.com/rss", "source": "Ocean News & Technology", "category": "marine"},
    {"url": "https://www.surfer.com/feed/", "source": "Surfer", "category": "marine"},
    # Archaeology (NEW)
    {"url": "https://www.archaeology.org/feed", "source": "Archaeology Magazine", "category": "archaeology"},
    {"url": "https://www.heritagedaily.com/feed", "source": "HeritageDaily", "category": "archaeology"},
    {"url": "https://www.livescience.com/feeds/all", "source": "Live Science", "category": "archaeology"},
    {"url": "https://archaeologynewsnetwork.blogspot.com/feeds/posts/default?alt=rss", "source": "Archaeology News Network", "category": "archaeology"},
    {"url": "https://populararchaeology.com/feed/", "source": "Popular Archaeology", "category": "archaeology"},
    # Volunteering & Social Impact (NEW)
    {"url": "https://ssir.org/site/rss", "source": "Stanford Social Innovation Review", "category": "social_impact"},
    {"url": "https://www.devex.com/news/rss", "source": "Devex", "category": "social_impact"},
    {"url": "https://philanthropynewsdigest.org/rss", "source": "Philanthropy News Digest", "category": "social_impact"},
    {"url": "https://nextcity.org/feed", "source": "Next City", "category": "social_impact"},
    {"url": "https://www.globalcitizen.org/en/feed/", "source": "Global Citizen", "category": "social_impact"},

    # Urban Planning & Transportation
    {"url": "https://www.strongtowns.org/journal?format=rss", "source": "Strong Towns", "category": "urban_planning"},
    {"url": "https://citymonitor.ai/feed", "source": "City Monitor", "category": "urban_planning"},
    {"url": "https://www.planetizen.com/feed", "source": "Planetizen", "category": "urban_planning"},
    {"url": "https://usa.streetsblog.org/feed/", "source": "Streetsblog USA", "category": "urban_planning"},
    {"url": "https://www.bloomberg.com/citylab/feed", "source": "Bloomberg CityLab", "category": "urban_planning"},

    # Agriculture & Farming
    {"url": "https://www.agweb.com/rss.xml", "source": "AgWeb", "category": "agriculture"},
    {"url": "https://modernfarmer.com/feed/", "source": "Modern Farmer", "category": "agriculture"},
    {"url": "https://civileats.com/feed/", "source": "Civil Eats", "category": "agriculture"},
    {"url": "https://www.agriculture.com/rss/all", "source": "Successful Farming", "category": "agriculture"},
    {"url": "https://thefern.org/feed/", "source": "Food & Environment Reporting Network", "category": "agriculture"},

    # Mental Health & Psychology
    {"url": "https://psyche.co/feed", "source": "Psyche", "category": "mental_health"},
    {"url": "https://www.psychologytoday.com/us/blog/feed", "source": "Psychology Today Blog", "category": "mental_health"},
    {"url": "https://theconversation.com/us/topics/mental-health-702/articles.atom", "source": "The Conversation Mental Health", "category": "mental_health"},
    {"url": "https://www.verywellmind.com/feed", "source": "Verywell Mind", "category": "mental_health"},
    {"url": "https://www.mind.org.uk/news/feed/", "source": "Mind UK", "category": "mental_health"},
    # Cryptocurrency
    {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk", "category": "cryptocurrency"},
    {"url": "https://cointelegraph.com/rss", "source": "CoinTelegraph", "category": "cryptocurrency"},
    {"url": "https://decrypt.co/feed", "source": "Decrypt", "category": "cryptocurrency"},
    {"url": "https://thedefiant.io/feed", "source": "The Defiant", "category": "cryptocurrency"},
    {"url": "https://bitcoinmagazine.com/.rss/full/", "source": "Bitcoin Magazine", "category": "cryptocurrency"},
    # Entertainment
    {"url": "https://deadline.com/feed/", "source": "Deadline", "category": "entertainment"},
    {"url": "https://variety.com/feed/", "source": "Variety", "category": "entertainment"},
    {"url": "https://www.hollywoodreporter.com/feed/", "source": "The Hollywood Reporter", "category": "entertainment"},
    {"url": "https://collider.com/feed/", "source": "Collider", "category": "entertainment"},
    {"url": "https://screenrant.com/feed/", "source": "Screen Rant", "category": "entertainment"},
    # Space
    {"url": "https://www.space.com/feeds/all", "source": "Space.com", "category": "space"},
    {"url": "https://spacenews.com/feed/", "source": "SpaceNews", "category": "space"},
    {"url": "https://www.nasaspaceflight.com/feed/", "source": "NASASpaceFlight", "category": "space"},
    {"url": "https://www.planetary.org/feeds/articles.rss", "source": "The Planetary Society", "category": "space"},
    {"url": "https://skyandtelescope.org/feed/", "source": "Sky & Telescope", "category": "space"},
    # Legal
    {"url": "https://www.lawfaremedia.org/feed", "source": "Lawfare", "category": "legal"},
    {"url": "https://www.scotusblog.com/feed/", "source": "SCOTUSblog", "category": "legal"},
    {"url": "https://abovethelaw.com/feed/", "source": "Above the Law", "category": "legal"},
    {"url": "https://www.law.com/rss/", "source": "Law.com", "category": "legal"},
    {"url": "https://www.jurist.org/news/feed/", "source": "JURIST", "category": "legal"},
    # Data Privacy
    {"url": "https://spreadprivacy.com/rss/", "source": "DuckDuckGo Blog", "category": "data_privacy"},
    {"url": "https://www.eff.org/rss/updates.xml", "source": "EFF", "category": "data_privacy"},
    {"url": "https://iapp.org/rss/", "source": "IAPP", "category": "data_privacy"},
    {"url": "https://www.accessnow.org/feed/", "source": "Access Now", "category": "data_privacy"},
    {"url": "https://edri.org/feed/", "source": "EDRi", "category": "data_privacy"},
    # Sustainability
    {"url": "https://www.greenbiz.com/rss/all", "source": "GreenBiz", "category": "sustainability"},
    {"url": "https://www.triplepundit.com/feed/", "source": "TriplePundit", "category": "sustainability"},
    {"url": "https://www.circularonline.co.uk/feed/", "source": "Circular", "category": "sustainability"},
    {"url": "https://www.edie.net/rss/news/", "source": "edie", "category": "sustainability"},
    {"url": "https://sustainability-magazine.com/rss/articles", "source": "Sustainability Magazine", "category": "sustainability"},
    # Accessibility
    {"url": "https://www.a11yproject.com/feed/feed.xml", "source": "A11Y Project", "category": "accessibility"},
    {"url": "https://www.deque.com/blog/feed/", "source": "Deque Blog", "category": "accessibility"},
    {"url": "https://adrianroselli.com/feed", "source": "Adrian Roselli", "category": "accessibility"},
    {"url": "https://www.scottohara.me/feed.xml", "source": "Scott O'Hara", "category": "accessibility"},
    {"url": "https://tink.uk/feed.xml", "source": "Tink (Léonie Watson)", "category": "accessibility"},
    # Transportation
    {"url": "https://www.thedrive.com/feed", "source": "The Drive", "category": "transportation"},
    {"url": "https://www.railway-technology.com/feed/", "source": "Railway Technology", "category": "transportation"},
    {"url": "https://www.smartcitiesdive.com/feeds/news/", "source": "Smart Cities Dive", "category": "transportation"},
    {"url": "https://www.flightglobal.com/rss", "source": "FlightGlobal", "category": "transportation"},
    {"url": "https://thelogisticsworld.com/feed/", "source": "The Logistics World", "category": "transportation"},
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
