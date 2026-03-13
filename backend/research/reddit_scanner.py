"""
Reddit scanner — fetches public Reddit posts for topic research.

Uses Reddit's public JSON API (no auth required).
Rate limited to 1 request per 2 seconds.
"""
import asyncio
from datetime import datetime, timezone

import httpx

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_USER_AGENT = "BlogPilot/1.0 (topic research)"
_BASE_URL = "https://www.reddit.com"
_RATE_LIMIT_SECONDS = 2


async def scan_subreddits(
    subreddits: list[str] | None = None,
    limit: int = 25,
) -> list[dict]:
    """
    Fetch hot posts from configured subreddits.

    Args:
        subreddits: List of subreddit names. Defaults to config.
        limit: Max posts per subreddit.

    Returns:
        List of dicts: {title, text, url, upvotes, num_comments, subreddit}
    """
    if subreddits is None:
        subreddits = cfg_get("research.reddit.subreddits", [
            "BusinessIntelligence", "datascience", "analytics",
            "PowerBI", "dataengineering",
        ])

    if not subreddits:
        logger.info("RedditScanner: no subreddits configured, skipping")
        return []

    per_sub = cfg_get("research.reddit.posts_per_subreddit", limit)
    all_posts = []

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=15.0,
        follow_redirects=True,
    ) as client:
        for i, sub in enumerate(subreddits):
            if i > 0:
                await asyncio.sleep(_RATE_LIMIT_SECONDS)
            try:
                posts = await _fetch_subreddit(client, sub, per_sub)
                all_posts.extend(posts)
                logger.debug(f"RedditScanner: r/{sub} → {len(posts)} posts")
            except Exception as e:
                logger.warning(f"RedditScanner: r/{sub} failed — {e}")

    logger.info(f"RedditScanner: fetched {len(all_posts)} posts from {len(subreddits)} subreddits")
    return all_posts


async def _fetch_subreddit(
    client: httpx.AsyncClient,
    subreddit: str,
    limit: int,
) -> list[dict]:
    """Fetch hot posts from a single subreddit."""
    url = f"{_BASE_URL}/r/{subreddit}/hot.json"
    resp = await client.get(url, params={"limit": limit, "raw_json": 1})
    resp.raise_for_status()

    data = resp.json()
    children = data.get("data", {}).get("children", [])

    posts = []
    for child in children:
        post_data = child.get("data", {})
        if post_data.get("stickied"):
            continue
        posts.append(_extract_post_data(post_data, subreddit))

    return posts


def _extract_post_data(post: dict, subreddit: str) -> dict:
    """Extract relevant fields from a Reddit post JSON object."""
    created_utc = post.get("created_utc", 0)
    return {
        "title": post.get("title", ""),
        "text": (post.get("selftext", "") or "")[:2000],
        "url": f"https://www.reddit.com{post.get('permalink', '')}",
        "upvotes": post.get("ups", 0),
        "num_comments": post.get("num_comments", 0),
        "subreddit": subreddit,
        "created_at": datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat() if created_utc else None,
        "source": "REDDIT",
    }
