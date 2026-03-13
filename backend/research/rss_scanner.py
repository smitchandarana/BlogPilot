"""
RSS/Atom feed scanner — fetches recent articles from curated industry feeds.

Uses feedparser library for robust RSS/Atom parsing.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from time import mktime

import httpx

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_USER_AGENT = "BlogPilot/1.0 (topic research)"

# Default feeds if none configured
_DEFAULT_FEEDS = [
    "https://towardsdatascience.com/feed",
    "https://feeds.feedburner.com/AnalyticsVidhya",
]


async def scan_feeds(
    feed_urls: list[str] | None = None,
    max_age_hours: int = 72,
) -> list[dict]:
    """
    Fetch and parse RSS/Atom feeds, returning recent entries.

    Args:
        feed_urls: List of feed URLs. Defaults to config.
        max_age_hours: Only return entries newer than this.

    Returns:
        List of dicts: {title, summary, url, published, source_name, source}
    """
    import feedparser

    if feed_urls is None:
        feed_urls = cfg_get("research.rss.feeds", _DEFAULT_FEEDS)

    if not feed_urls:
        logger.info("RSSScanner: no feeds configured, skipping")
        return []

    max_age = cfg_get("research.rss.max_age_hours", max_age_hours)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age)
    all_entries = []

    async with httpx.AsyncClient(
        headers={"User-Agent": _USER_AGENT},
        timeout=15.0,
        follow_redirects=True,
    ) as client:
        for feed_url in feed_urls:
            try:
                resp = await client.get(feed_url)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                feed_title = feed.feed.get("title", feed_url)

                for entry in feed.entries:
                    parsed = _parse_entry(entry, feed_title, cutoff)
                    if parsed:
                        all_entries.append(parsed)

                logger.debug(f"RSSScanner: {feed_title} → {len(feed.entries)} entries")
            except Exception as e:
                logger.warning(f"RSSScanner: {feed_url} failed — {e}")

    logger.info(f"RSSScanner: fetched {len(all_entries)} entries from {len(feed_urls)} feeds")
    return all_entries


def _parse_entry(entry: dict, feed_title: str, cutoff: datetime) -> dict | None:
    """Parse a single feed entry, returning None if too old."""
    # Parse published date
    published_dt = None
    published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if published_parsed:
        try:
            published_dt = datetime.fromtimestamp(mktime(published_parsed), tz=timezone.utc)
        except (ValueError, OverflowError):
            pass

    # Skip entries older than cutoff
    if published_dt and published_dt < cutoff:
        return None

    # Extract summary, strip HTML tags roughly
    summary = entry.get("summary", "") or entry.get("description", "") or ""
    summary = _strip_html(summary)[:1000]

    return {
        "title": entry.get("title", ""),
        "summary": summary,
        "url": entry.get("link", ""),
        "published": published_dt.isoformat() if published_dt else None,
        "source_name": feed_title,
        "source": "RSS",
    }


def _strip_html(text: str) -> str:
    """Rough HTML tag stripping."""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
