"""
Feed scanner — Sprint 4.

Navigates to the LinkedIn feed, scrolls to load posts, extracts post data
from the DOM, and filters out posts already seen in the database.
"""
import re
from typing import List, Optional

from playwright.async_api import Page

from backend.automation.human_behavior import scroll_down, random_delay
from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)

LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


class FeedScanner:
    """
    Scans the LinkedIn feed and returns new, unseen posts.
    """

    async def scan(self, page: Page, db=None) -> List[dict]:
        """
        Navigate to feed, scroll, extract posts, and deduplicate.
        Returns list of post dicts (new posts only, capped at max_posts_per_scan).
        """
        logger.info("Feed scan starting")

        # Navigate to feed if not already there
        if "linkedin.com/feed" not in page.url:
            await page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=30000)
            await random_delay(2.0, 4.0)

        # Scroll to load posts
        scroll_passes = int(cfg_get("feed_engagement.scroll_passes", 3))
        await scroll_down(page, scroll_passes)

        # Extract all posts from DOM
        posts = await self._extract_posts(page)
        logger.info(f"Extracted {len(posts)} posts from DOM")

        # Deduplicate against DB
        if db is not None:
            posts = self._filter_seen(posts, db)
            logger.info(f"After deduplication: {len(posts)} new posts")

        max_posts = int(cfg_get("feed_engagement.max_posts_per_scan", 30))
        result = posts[:max_posts]
        logger.info(f"Feed scan complete — returning {len(result)} posts")
        return result

    async def _extract_posts(self, page: Page) -> List[dict]:
        """Parse the LinkedIn feed DOM and return raw post dicts."""
        posts = []

        # Wait for feed container
        try:
            await page.wait_for_selector(
                "div.scaffold-finite-scroll__content, "
                "div[data-finite-scroll-hotspot-size]",
                timeout=10000,
            )
        except Exception:
            logger.warning("Feed container not found — page may not have loaded properly")
            return posts

        # Find post containers: data-urn identifies activity updates
        post_elements = await page.query_selector_all(
            "div[data-urn*='activity'], "
            "div[data-id*='urn:li:activity']"
        )

        if not post_elements:
            # Broader fallback selector
            post_elements = await page.query_selector_all(
                "div.feed-shared-update-v2, "
                "div.occludable-update"
            )

        logger.debug(f"Found {len(post_elements)} post containers in DOM")

        for el in post_elements:
            try:
                post = await self._parse_post(el)
                if post:
                    posts.append(post)
            except Exception as e:
                logger.debug(f"Post parse error: {e}")
                continue

        return posts

    async def _parse_post(self, el) -> Optional[dict]:
        """Extract data from a single post container element."""

        # ── URL ────────────────────────────────────────────────────────────
        url = await self._extract_url(el)
        if not url:
            return None  # Can't track or deduplicate without URL

        # ── Author name ────────────────────────────────────────────────────
        author_el = await el.query_selector(
            "span.update-components-actor__name span[aria-hidden='true'], "
            "span.update-components-actor__name"
        )
        author_name = _clean(await author_el.inner_text()) if author_el else "Unknown"

        # ── Author profile URL ─────────────────────────────────────────────
        author_link = await el.query_selector(
            "a.update-components-actor__meta-link, "
            "a[href*='/in/'], a[href*='/company/']"
        )
        author_url = ""
        if author_link:
            href = await author_link.get_attribute("href") or ""
            author_url = _normalise_url(href)

        # ── Post text ──────────────────────────────────────────────────────
        text_el = await el.query_selector(
            "div.feed-shared-update-v2__description, "
            "div.update-components-text, "
            "span.break-words"
        )
        text = _clean(await text_el.inner_text()) if text_el else ""
        if not text:
            return None  # Skip ads / empty posts

        # ── Like count ─────────────────────────────────────────────────────
        like_el = await el.query_selector(
            "span.social-details-social-counts__reactions-count, "
            "button[aria-label*='reaction'] span"
        )
        like_count = _parse_count(await like_el.inner_text()) if like_el else 0

        # ── Comment count ──────────────────────────────────────────────────
        comment_el = await el.query_selector(
            "button[aria-label*='comment'] "
            "span.social-details-social-counts__item-designation, "
            "li.social-details-social-counts__item--right-aligned span"
        )
        comment_count = _parse_count(await comment_el.inner_text()) if comment_el else 0

        # ── Timestamp text (e.g. "2h", "1d") ──────────────────────────────
        time_el = await el.query_selector(
            "span.update-components-actor__sub-description "
            "span[aria-hidden='true'], "
            "time"
        )
        timestamp_text = _clean(await time_el.inner_text()) if time_el else ""

        return {
            "url": url,
            "author_name": author_name,
            "author_url": author_url,
            "text": text,
            "like_count": like_count,
            "comment_count": comment_count,
            "timestamp_text": timestamp_text,
        }

    async def _extract_url(self, el) -> Optional[str]:
        """Extract the canonical URL for a post."""
        # Prefer data-urn attribute (most reliable)
        urn = await el.get_attribute("data-urn") or ""
        if "activity:" in urn:
            activity_id = urn.split("activity:")[-1].split(",")[0]
            return f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"

        # Fallback: find a link to the post
        link_el = await el.query_selector(
            "a[href*='/feed/update/'], "
            "a[href*='/posts/']"
        )
        if link_el:
            href = await link_el.get_attribute("href") or ""
            return _normalise_url(href)

        return None

    def _filter_seen(self, posts: List[dict], db) -> List[dict]:
        """Return only posts not already in the database."""
        from backend.storage.post_state import is_seen
        return [p for p in posts if not is_seen(p["url"], db)]


# ── Helpers ────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Strip HTML artefacts and normalise whitespace."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalise_url(href: str) -> str:
    """Return an absolute LinkedIn URL, stripping query params."""
    if not href:
        return ""
    if href.startswith("http"):
        return href.split("?")[0]
    return f"https://www.linkedin.com{href.split('?')[0]}"


def _parse_count(text: str) -> int:
    """Parse LinkedIn engagement counts: '1.2K' → 1200, '34' → 34."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    upper = text.upper()
    try:
        if "K" in upper:
            return int(float(upper.replace("K", "")) * 1000)
        if "M" in upper:
            return int(float(upper.replace("M", "")) * 1_000_000)
        return int(text)
    except ValueError:
        return 0
