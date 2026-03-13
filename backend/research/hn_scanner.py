"""
Hacker News scanner — fetches top stories from the HN Firebase API.

Optional source, disabled by default in config.
"""
import asyncio
from datetime import datetime, timezone

import httpx

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_API_BASE = "https://hacker-news.firebaseio.com/v0"


async def scan_top_stories(limit: int = 30) -> list[dict]:
    """
    Fetch top stories from Hacker News.

    Args:
        limit: Max stories to fetch.

    Returns:
        List of dicts: {title, url, score, num_comments, source}
    """
    limit = cfg_get("research.hackernews.top_stories_limit", limit)

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{_API_BASE}/topstories.json")
            resp.raise_for_status()
            story_ids = resp.json()[:limit]
        except Exception as e:
            logger.warning(f"HNScanner: failed to fetch top stories — {e}")
            return []

        # Fetch story details in batches of 10
        stories = []
        for i in range(0, len(story_ids), 10):
            batch = story_ids[i:i + 10]
            tasks = [_fetch_item(client, sid) for sid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    stories.append(r)

    logger.info(f"HNScanner: fetched {len(stories)} stories")
    return stories


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> dict:
    """Fetch a single HN item by ID."""
    resp = await client.get(f"{_API_BASE}/item/{item_id}.json")
    resp.raise_for_status()
    data = resp.json()

    if not data or data.get("type") != "story":
        return {}

    created = data.get("time", 0)
    return {
        "title": data.get("title", ""),
        "url": data.get("url", ""),
        "score": data.get("score", 0),
        "num_comments": data.get("descendants", 0),
        "created_at": datetime.fromtimestamp(created, tz=timezone.utc).isoformat() if created else None,
        "source": "HN",
    }
