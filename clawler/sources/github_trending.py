"""GitHub Trending source — scrapes trending repos and developers (no API key needed)."""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

GITHUB_TRENDING_URL = "https://github.com/trending"
GITHUB_TRENDING_DEVS_URL = "https://github.com/trending/developers"

# Map GitHub language names to broader categories
LANGUAGE_CATEGORIES = {
    "python": "ai",
    "jupyter notebook": "ai",
    "rust": "programming",
    "go": "programming",
    "c": "programming",
    "c++": "programming",
    "java": "programming",
    "kotlin": "programming",
    "swift": "programming",
    "typescript": "programming",
    "javascript": "programming",
    "ruby": "programming",
    "php": "programming",
    "html": "programming",
    "css": "design",
    "scss": "design",
    "shell": "programming",
    "dockerfile": "programming",
    "hcl": "programming",
    "solidity": "crypto",
    "move": "crypto",
}


class GitHubTrendingSource(BaseSource):
    """Crawl GitHub Trending page for trending repositories and developers."""

    name = "github_trending"

    def __init__(
        self,
        since: str = "daily",
        spoken_language: str = "",
        programming_language: str = "",
        include_developers: bool = False,
        time_ranges: Optional[List[str]] = None,
    ):
        """
        Args:
            since: Default time range — 'daily', 'weekly', or 'monthly'.
            spoken_language: Filter by spoken language code (e.g. 'en').
            programming_language: Filter by programming language (e.g. 'python').
            include_developers: Also scrape trending developers page.
            time_ranges: Scrape multiple time ranges (e.g. ['daily', 'weekly']).
                         Overrides `since` when provided. Deduplicates across ranges.
        """
        self.since = since
        self.spoken_language = spoken_language
        self.programming_language = programming_language
        self.include_developers = include_developers
        self.time_ranges = time_ranges or [since]

    def _build_url(self, base: str, since: str) -> str:
        parts = [f"since={since}"]
        if self.spoken_language:
            parts.append(f"spoken_language_code={self.spoken_language}")
        if self.programming_language:
            lang = self.programming_language.lower().replace(" ", "-").replace("+", "%2B")
            return f"{base}/{lang}?{'&'.join(parts)}"
        return f"{base}?{'&'.join(parts)}"

    @staticmethod
    def _parse_number(text: str) -> int:
        """Parse '1,234' or '1.2k' style numbers."""
        text = text.strip().replace(",", "")
        m = re.match(r"([\d.]+)\s*k", text, re.IGNORECASE)
        if m:
            return int(float(m.group(1)) * 1000)
        try:
            return int(float(text))
        except (ValueError, TypeError):
            return 0

    def _scrape_repos(self, since: str) -> List[Article]:
        url = self._build_url(GITHUB_TRENDING_URL, since)
        html = self.fetch_url(url)
        if not html:
            return []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.warning(f"[GitHubTrending] Parse error: {e}")
            return []

        articles = []
        rows = soup.select("article.Box-row")
        for rank, row in enumerate(rows[:25], 1):
            try:
                h2 = row.select_one("h2 a")
                if not h2:
                    continue
                repo_path = h2.get("href", "").strip().lstrip("/")
                if not repo_path:
                    continue
                repo_name = repo_path.replace("/", " / ")
                repo_url = f"https://github.com/{repo_path}"

                desc_el = row.select_one("p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                # Language
                lang_el = row.select_one("span[itemprop='programmingLanguage']")
                language = lang_el.get_text(strip=True) if lang_el else ""

                # Total stars & forks from the small links
                total_stars = 0
                total_forks = 0
                stat_links = row.select("a.Link--muted.d-inline-block.mr-3")
                if not stat_links:
                    stat_links = row.select("a.Link--muted")
                for link in stat_links:
                    href = link.get("href", "")
                    text_val = link.get_text(strip=True)
                    if "/stargazers" in href:
                        total_stars = self._parse_number(text_val)
                    elif "/forks" in href or "/network" in href:
                        total_forks = self._parse_number(text_val)

                # Stars gained in period
                stars_today = ""
                stars_gained = 0
                gain_spans = row.select("span.d-inline-block.float-sm-right")
                if gain_spans:
                    stars_today = gain_spans[0].get_text(strip=True)
                    m = re.search(r"([\d,]+)", stars_today.replace(",", ""))
                    if m:
                        stars_gained = int(m.group(1))

                # Build rich summary
                meta = []
                if language:
                    meta.append(language)
                if total_stars:
                    meta.append(f"⭐ {total_stars:,}")
                if total_forks:
                    meta.append(f"🍴 {total_forks:,}")
                if stars_today:
                    meta.append(f"📈 {stars_today}")

                summary_parts = []
                if meta:
                    summary_parts.append(" · ".join(meta))
                if description:
                    summary_parts.append(description[:200])
                summary = " | ".join(summary_parts)

                # Determine category from language
                cat = "tech"
                if language:
                    cat = LANGUAGE_CATEGORIES.get(language.lower(), "tech")

                tags = [f"gh-trending:{since}"]
                if language:
                    tags.append(f"lang:{language.lower()}")
                tags.append(f"rank:{rank}")

                articles.append(Article(
                    title=f"🔥 {repo_name}",
                    url=repo_url,
                    source=f"GitHub Trending ({since})",
                    summary=summary[:300],
                    timestamp=datetime.now(timezone.utc),
                    category=cat,
                    tags=tags,
                ))
            except Exception as e:
                logger.debug(f"[GitHubTrending] Failed to parse row: {e}")
                continue

        logger.info(f"[GitHubTrending] Found {len(articles)} trending repos ({since})")
        return articles

    def _scrape_developers(self) -> List[Article]:
        url = self._build_url(GITHUB_TRENDING_DEVS_URL, self.since)
        html = self.fetch_url(url)
        if not html:
            return []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.warning(f"[GitHubTrending] Dev parse error: {e}")
            return []

        articles = []
        rows = soup.select("article.Box-row")
        for rank, row in enumerate(rows[:25], 1):
            try:
                name_link = row.select_one("h1.h3 a")
                if not name_link:
                    continue
                username = name_link.get("href", "").strip().lstrip("/")
                display_name_el = row.select_one("h1.h3 a span.text-normal")
                if display_name_el:
                    display_name = name_link.get_text(strip=True).replace(display_name_el.get_text(strip=True), "").strip()
                else:
                    display_name = username

                profile_url = f"https://github.com/{username}"

                # Popular repo
                repo_el = row.select_one("article h1 a") or row.select_one(".mt-1 a")
                repo_desc = ""
                repo_name = ""
                if repo_el:
                    repo_name = repo_el.get_text(strip=True)
                    repo_desc_el = row.select_one("article .f6, .mt-1 + .f6")
                    if repo_desc_el:
                        repo_desc = repo_desc_el.get_text(strip=True)

                summary = f"Trending developer #{rank}"
                if repo_name:
                    summary += f" — popular repo: {repo_name}"
                if repo_desc:
                    summary += f" ({repo_desc[:100]})"

                articles.append(Article(
                    title=f"👨‍💻 {display_name or username} (@{username})",
                    url=profile_url,
                    source="GitHub Trending Developers",
                    summary=summary[:300],
                    timestamp=datetime.now(timezone.utc),
                    category="tech",
                    tags=[f"gh-dev-trending:{self.since}", f"rank:{rank}"],
                ))
            except Exception as e:
                logger.debug(f"[GitHubTrending] Failed to parse dev row: {e}")
                continue

        logger.info(f"[GitHubTrending] Found {len(articles)} trending developers")
        return articles

    def crawl(self) -> List[Article]:
        seen_urls = set()
        articles = []

        for time_range in self.time_ranges:
            for article in self._scrape_repos(time_range):
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    articles.append(article)

        if self.include_developers:
            for article in self._scrape_developers():
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    articles.append(article)

        logger.info(f"[GitHubTrending] Total: {len(articles)} articles (deduped)")
        return articles
