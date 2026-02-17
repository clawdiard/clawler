"""Lemmy source — fetches trending posts from Lemmy instances via public API (no auth needed)."""
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from clawler.models import Article
from clawler.sources.base import BaseSource

logger = logging.getLogger(__name__)

# Popular Lemmy instances with diverse communities
LEMMY_INSTANCES = [
    {"url": "https://lemmy.world", "name": "lemmy.world"},
    {"url": "https://lemmy.ml", "name": "lemmy.ml"},
    {"url": "https://programming.dev", "name": "programming.dev"},
    {"url": "https://lemm.ee", "name": "lemm.ee"},
    {"url": "https://sh.itjust.works", "name": "sh.itjust.works"},
    {"url": "https://sopuli.xyz", "name": "sopuli.xyz"},
    {"url": "https://feddit.de", "name": "feddit.de"},
    {"url": "https://discuss.tchncs.de", "name": "discuss.tchncs.de"},
]

VALID_SORTS = ("Hot", "Active", "New", "TopDay", "TopWeek", "TopMonth", "MostComments")

# Specific keyword categories (checked first)
_SPECIFIC_KEYWORDS: Dict[str, List[str]] = {
    "ai": ["ai", "artificial", "machinelearning", "deeplearning", "llm", "chatgpt",
           "openai", "neural", "gpt", "copilot", "diffusion", "transformer", "langchain"],
    "security": ["cybersecurity", "privacy", "netsec", "infosec", "hacking", "vulnerability",
                 "malware", "encryption", "vpn", "tor", "opsec", "exploit", "ransomware"],
    "crypto": ["cryptocurrency", "bitcoin", "ethereum", "crypto", "blockchain", "defi",
               "web3", "nft", "solana", "monero"],
    "science": ["science", "physics", "biology", "chemistry", "astronomy", "space",
                "climate", "environment", "geology", "neuroscience", "paleontology"],
    "health": ["health", "medical", "medicine", "fitness", "nutrition", "mentalhealth",
               "psychology", "healthcare", "covid", "vaccine", "adhd"],
    "gaming": ["gaming", "games", "pcgaming", "retrogaming", "gamedev", "indiegaming",
               "emulation", "steam", "nintendo", "playstation", "xbox"],
    "design": ["design", "ui", "ux", "graphicdesign", "webdesign", "typography",
               "photography", "art", "illustration"],
    "business": ["business", "economics", "finance", "stocks", "entrepreneur",
                 "marketing", "realestate", "investing", "startup"],
    "world": ["worldnews", "news", "politics", "usanews", "europe", "unitedkingdom",
              "geopolitics", "war", "democracy", "elections", "activism"],
    "culture": ["books", "movies", "music", "television", "anime", "comics",
                "literature", "film", "podcasts", "history", "philosophy"],
    "education": ["education", "learning", "university", "askscience", "explainlikeimfive",
                  "teachers", "academia"],
}

# Generic tech communities (fallback)
_GENERIC_TECH = {"technology", "programming", "linux", "python", "rust", "golang",
                 "webdev", "selfhosted", "homelab", "opensource", "foss", "android",
                 "apple", "hardware", "nix", "haskell", "javascript", "cpp",
                 "typescript", "java", "dotnet", "docker", "kubernetes", "devops",
                 "vim", "neovim", "emacs", "git", "databases", "networking",
                 "sysadmin", "functionalProgramming", "lisp"}


def _map_category(community: str, title: str = "") -> str:
    """Backward-compatible alias for _detect_category."""
    return _detect_category(community, title)


def _detect_category(community: str, title: str = "") -> str:
    """Two-tier category detection: specific keywords first, then generic tech."""
    c = community.lower()
    text = f"{c} {title.lower()}"

    # Check specific categories first (exact community match)
    for cat, keywords in _SPECIFIC_KEYWORDS.items():
        if c in keywords:
            return cat

    # Check title keywords (whole-word match to avoid substring false positives)
    title_lower = title.lower()
    if title_lower:
        for cat, keywords in _SPECIFIC_KEYWORDS.items():
            for kw in keywords:
                if kw in title_lower.split():
                    return cat

    # Generic tech fallback
    if c in _GENERIC_TECH:
        return "tech"

    return "tech"  # Lemmy skews tech


def _quality_score(score: int, comments: int) -> float:
    """Logarithmic quality score 0–1 based on votes and comments.

    score=10/comments=5 ≈ 0.35, score=100/comments=30 ≈ 0.65, score=500/comments=100 ≈ 0.85
    """
    engagement = max(score, 0) + max(comments, 0) * 3
    if engagement <= 0:
        return 0.1
    raw = math.log10(1 + engagement) / math.log10(5000)
    return round(min(max(raw, 0.05), 1.0), 3)


def _human_count(n: int) -> str:
    """Format count as human-readable string."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class LemmySource(BaseSource):
    """Fetch trending posts from Lemmy instances via their public API."""

    name = "lemmy"

    def __init__(
        self,
        limit: int = 15,
        sort: str = "Hot",
        instances: Optional[List[dict]] = None,
        communities: Optional[List[str]] = None,
        exclude_communities: Optional[List[str]] = None,
        min_score: int = 0,
        min_comments: int = 0,
        min_quality: float = 0.0,
        category_filter: Optional[List[str]] = None,
        nsfw: bool = False,
        global_limit: Optional[int] = None,
    ):
        self.limit = limit
        self.sort = sort if sort in VALID_SORTS else "Hot"
        self.instances = instances or LEMMY_INSTANCES
        self.communities = [c.lower() for c in communities] if communities else None
        self.exclude_communities = {c.lower() for c in exclude_communities} if exclude_communities else set()
        self.min_score = min_score
        self.min_comments = min_comments
        self.min_quality = min_quality
        self.category_filter = set(category_filter) if category_filter else None
        self.nsfw = nsfw
        self.global_limit = global_limit

    def crawl(self) -> List[Article]:
        all_articles: List[Article] = []
        seen_urls: Set[str] = set()

        for instance in self.instances:
            try:
                articles = self._fetch_instance(instance, seen_urls)
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"[Lemmy] Failed to fetch {instance['name']}: {e}")

        # Sort by quality score descending
        all_articles.sort(key=lambda a: a.quality_score or 0, reverse=True)

        if self.global_limit:
            all_articles = all_articles[: self.global_limit]

        logger.info(f"[Lemmy] Fetched {len(all_articles)} posts across {len(self.instances)} instances")
        return all_articles

    def _fetch_instance(self, instance: dict, seen_urls: Set[str]) -> List[Article]:
        """Fetch posts from a single Lemmy instance."""
        if self.communities:
            # Fetch specific communities
            articles: List[Article] = []
            for comm in self.communities:
                try:
                    arts = self._fetch_community(instance, comm, seen_urls)
                    articles.extend(arts)
                except Exception as e:
                    logger.debug(f"[Lemmy] Failed community {comm}@{instance['name']}: {e}")
            return articles
        else:
            return self._fetch_all(instance, seen_urls)

    def _fetch_all(self, instance: dict, seen_urls: Set[str]) -> List[Article]:
        """Fetch posts from all communities on an instance."""
        api_url = f"{instance['url']}/api/v3/post/list?sort={self.sort}&limit={self.limit}&type_=All"
        data = self.fetch_json(api_url)
        if not data or "posts" not in data:
            return []
        return self._parse_posts(data["posts"], instance, seen_urls)

    def _fetch_community(self, instance: dict, community: str, seen_urls: Set[str]) -> List[Article]:
        """Fetch posts from a specific community."""
        api_url = (
            f"{instance['url']}/api/v3/post/list?sort={self.sort}&limit={self.limit}"
            f"&type_=All&community_name={community}"
        )
        data = self.fetch_json(api_url)
        if not data or "posts" not in data:
            return []
        return self._parse_posts(data["posts"], instance, seen_urls)

    def _parse_posts(self, posts: list, instance: dict, seen_urls: Set[str]) -> List[Article]:
        """Parse Lemmy API post views into Articles."""
        articles: List[Article] = []

        for post_view in posts[: self.limit]:
            try:
                post = post_view.get("post", {})
                community = post_view.get("community", {})
                counts = post_view.get("counts", {})

                title = post.get("name", "").strip()
                if not title:
                    continue

                # Skip NSFW unless enabled
                if not self.nsfw and (post.get("nsfw") or community.get("nsfw")):
                    continue

                # Use external link if available, otherwise the Lemmy post URL
                url = post.get("url") or f"{instance['url']}/post/{post.get('id', '')}"
                if not url:
                    continue

                # Deduplicate
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Discussion URL is always the Lemmy post page
                discussion_url = f"{instance['url']}/post/{post.get('id', '')}"

                # Timestamp
                ts = None
                published = post.get("published")
                if published:
                    try:
                        clean = published.replace("Z", "+00:00")
                        ts = datetime.fromisoformat(clean)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                    except (ValueError, AttributeError):
                        pass

                # Metadata
                score = counts.get("score", 0)
                comments = counts.get("comments", 0)
                community_name = community.get("name", "")
                community_title = community.get("title", community_name)

                # Filters
                if score < self.min_score:
                    continue
                if comments < self.min_comments:
                    continue

                # Exclude communities
                if community_name.lower() in self.exclude_communities:
                    continue

                # Author
                creator = post_view.get("creator", {})
                author = creator.get("name", "")

                # Category detection (keyword-based)
                category = _detect_category(community_name, title)

                # Category filter
                if self.category_filter and category not in self.category_filter:
                    continue

                # Quality score
                qs = _quality_score(score, comments)
                if qs < self.min_quality:
                    continue

                # Tags
                tags = [
                    f"lemmy:instance:{instance['name']}",
                    f"lemmy:community:{community_name}",
                    f"lemmy:category:{category}",
                ]
                if author:
                    tags.append(f"lemmy:author:{author}")
                if comments > 10:
                    tags.append("lemmy:has-discussion")

                # Summary
                summary_parts = []
                summary_parts.append(f"⬆ {_human_count(score)}")
                summary_parts.append(f"💬 {_human_count(comments)}")
                if community_title:
                    summary_parts.append(f"📂 {community_title}")
                summary_parts.append(f"🏠 {instance['name']}")

                source_label = f"Lemmy ({instance['name']})"

                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=source_label,
                        summary=" | ".join(summary_parts),
                        timestamp=ts,
                        category=category,
                        tags=tags,
                        author=author,
                        discussion_url=discussion_url,
                        quality_score=qs,
                    )
                )
            except Exception as e:
                logger.debug(f"[Lemmy] Skipping post: {e}")
                continue

        return articles
