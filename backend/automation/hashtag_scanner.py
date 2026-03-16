"""
Hashtag & content search scanner — Phase B2.

Scans LinkedIn hashtag pages and content search results to reach
new audiences beyond the home feed.

Usage:
    scanner = HashtagScanner()
    posts = await scanner.scan_multiple(page, hashtags, topics)
"""
import random
from typing import List, Optional

from playwright.async_api import Page

from backend.automation.human_behavior import random_delay, scroll_down
from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class HashtagScanner:
    """Scan LinkedIn hashtag feeds and content search results."""

    async def scan_hashtag(self, page: Page, hashtag: str) -> List[dict]:
        """
        Navigate to a hashtag feed page and extract posts.
        hashtag should be without the '#' prefix.
        """
        tag = hashtag.lstrip("#").strip()
        if not tag:
            return []

        url = f"https://www.linkedin.com/feed/hashtag/{tag}/"
        logger.info(f"HashtagScanner: scanning #{tag}")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await random_delay(2.0, 4.0)

            # Scroll to load more posts
            scroll_passes = int(cfg_get("feed_engagement.scroll_passes", 3))
            await scroll_down(page, passes=scroll_passes)

            posts = await self._extract_posts(page, source=f"hashtag:#{tag}")
            logger.info(f"HashtagScanner: found {len(posts)} posts from #{tag}")
            return posts
        except Exception as e:
            logger.warning(f"HashtagScanner: error scanning #{tag}: {e}")
            return []

    async def scan_search(self, page: Page, topic: str) -> List[dict]:
        """
        Navigate to LinkedIn content search results for a topic.
        """
        if not topic:
            return []

        from urllib.parse import quote
        url = f"https://www.linkedin.com/search/results/content/?keywords={quote(topic)}"
        logger.info(f"HashtagScanner: searching '{topic}'")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await random_delay(2.0, 4.0)

            scroll_passes = int(cfg_get("feed_engagement.scroll_passes", 3))
            await scroll_down(page, passes=scroll_passes)

            posts = await self._extract_posts(page, source=f"search:{topic}")
            logger.info(f"HashtagScanner: found {len(posts)} posts for '{topic}'")
            return posts
        except Exception as e:
            logger.warning(f"HashtagScanner: error searching '{topic}': {e}")
            return []

    async def scan_multiple(
        self, page: Page, hashtags: List[str], topics: List[str]
    ) -> List[dict]:
        """
        Pick a random subset of hashtags and topics to scan.
        Limits: hashtag_scan_count hashtags, search_scan_count topics per session.
        """
        all_posts: List[dict] = []

        hashtag_count = int(cfg_get("feed_engagement.hashtag_scan_count", 3))
        search_count = int(cfg_get("feed_engagement.search_scan_count", 2))

        # Pick random subset to avoid detection patterns
        selected_hashtags = random.sample(hashtags, min(hashtag_count, len(hashtags))) if hashtags else []
        selected_topics = random.sample(topics, min(search_count, len(topics))) if topics else []

        for tag in selected_hashtags:
            posts = await self.scan_hashtag(page, tag)
            all_posts.extend(posts)
            await random_delay(3.0, 8.0)  # delay between hashtag pages

        for topic in selected_topics:
            posts = await self.scan_search(page, topic)
            all_posts.extend(posts)
            await random_delay(3.0, 8.0)

        logger.info(
            f"HashtagScanner: scan_multiple complete — "
            f"{len(selected_hashtags)} hashtags, {len(selected_topics)} topics, "
            f"{len(all_posts)} total posts"
        )
        return all_posts

    async def _extract_posts(self, page: Page, source: str = "") -> List[dict]:
        """
        Extract posts from the current page using the same DOM selectors
        as FeedScanner. Returns list of post dicts.
        """
        posts = []

        # Wait for feed container
        try:
            await page.wait_for_selector(
                "div.scaffold-finite-scroll__content, "
                "div[data-finite-scroll-hotspot-size], "
                "div.search-results-container",
                timeout=10000,
            )
        except Exception:
            logger.debug(f"HashtagScanner: feed container not found for {source}")
            return posts

        # Post containers
        post_elements = await page.query_selector_all(
            "div[data-urn*='activity'], "
            "div[data-id*='urn:li:activity']"
        )

        if not post_elements:
            post_elements = await page.query_selector_all(
                "div.feed-shared-update-v2, "
                "div.occludable-update"
            )

        max_posts = int(cfg_get("feed_engagement.max_posts_per_scan", 30))

        for el in post_elements[:max_posts]:
            try:
                post = await self._parse_post(el, source)
                if post:
                    posts.append(post)
            except Exception:
                continue

        return posts

    async def _parse_post(self, el, source: str) -> Optional[dict]:
        """Extract data from a single post container element."""
        # URL
        url = await self._extract_url(el)
        if not url:
            return None

        # Author name
        author_name = "Unknown"
        for sel in [
            "span.update-components-actor__name span[aria-hidden='true']",
            "span.update-components-actor__name",
            "span.feed-shared-actor__name span[aria-hidden='true']",
            "span.feed-shared-actor__name",
            ".update-components-actor__title span[dir='ltr'] span[aria-hidden='true']",
        ]:
            author_el = await el.query_selector(sel)
            if author_el:
                name = (await author_el.inner_text()).strip()
                if name and name != "Unknown" and len(name) < 100:
                    author_name = name
                    break

        # Author URL
        author_link = await el.query_selector(
            "a.update-components-actor__meta-link, "
            "a.update-components-actor__container-link, "
            "a[href*='/in/'], a[href*='/company/']"
        )
        author_url = ""
        if author_link:
            href = await author_link.get_attribute("href") or ""
            if href.startswith("http"):
                author_url = href.split("?")[0]

        # Post text
        text_el = await el.query_selector(
            "div.feed-shared-update-v2__description, "
            "div.update-components-text, "
            "span.break-words"
        )
        text = (await text_el.inner_text()).strip() if text_el else ""
        if not text:
            return None

        # Counts
        like_el = await el.query_selector(
            "span.social-details-social-counts__reactions-count, "
            "button[aria-label*='reaction'] span"
        )
        like_count = self._parse_count(await like_el.inner_text()) if like_el else 0

        comment_el = await el.query_selector(
            "button[aria-label*='comment'] span"
        )
        comment_count = self._parse_count(await comment_el.inner_text()) if comment_el else 0

        return {
            "url": url,
            "author_name": author_name,
            "author_url": author_url,
            "text": text,
            "like_count": like_count,
            "comment_count": comment_count,
            "source": source,
        }

    async def _extract_url(self, el) -> str:
        """Extract the post's permanent URL."""
        for sel in [
            "a[href*='/feed/update/']",
            "a[href*='/posts/']",
            "a[href*='activity']",
        ]:
            link = await el.query_selector(sel)
            if link:
                href = await link.get_attribute("href") or ""
                if href.startswith("http"):
                    return href.split("?")[0]

        # Fallback: data-urn attribute
        urn = await el.get_attribute("data-urn") or await el.get_attribute("data-id") or ""
        if "activity:" in urn:
            activity_id = urn.split("activity:")[-1].split(")")[0]
            return f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"

        return ""

    @staticmethod
    def _parse_count(text: str) -> int:
        """Parse '1,234' or '1K' into an integer."""
        text = text.strip().replace(",", "")
        if not text:
            return 0
        try:
            if text.upper().endswith("K"):
                return int(float(text[:-1]) * 1000)
            return int(text)
        except ValueError:
            return 0
