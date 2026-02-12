"""GitHub Trending source — scrapes trending repos (no API key needed)."""
import logging
from datetime import datetime, timezone
from typing import List
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

GITHUB_TRENDING_URL = "https://github.com/trending"


class GitHubTrendingSource(BaseSource):
    """Crawl GitHub Trending page for trending repositories."""

    name = "github_trending"

    def __init__(self, since: str = "daily", spoken_language: str = ""):
        self.since = since
        self.spoken_language = spoken_language

    def crawl(self) -> List[Article]:
        url = f"{GITHUB_TRENDING_URL}?since={self.since}"
        if self.spoken_language:
            url += f"&spoken_language_code={self.spoken_language}"

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
        for row in rows[:25]:
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

                # Extract stars today
                stars_today = ""
                spans = row.select("span.d-inline-block.float-sm-right")
                if spans:
                    stars_today = spans[0].get_text(strip=True)

                # Extract language
                lang_el = row.select_one("span[itemprop='programmingLanguage']")
                language = lang_el.get_text(strip=True) if lang_el else ""

                summary_parts = []
                if language:
                    summary_parts.append(f"Language: {language}")
                if stars_today:
                    summary_parts.append(stars_today)
                if description:
                    summary_parts.append(description[:200])
                summary = " | ".join(summary_parts)

                articles.append(Article(
                    title=f"🔥 {repo_name}",
                    url=repo_url,
                    source="GitHub Trending",
                    summary=summary[:300],
                    timestamp=datetime.now(timezone.utc),
                    category="tech",
                ))
            except Exception as e:
                logger.debug(f"[GitHubTrending] Failed to parse row: {e}")
                continue

        logger.info(f"[GitHubTrending] Found {len(articles)} trending repos")
        return articles
