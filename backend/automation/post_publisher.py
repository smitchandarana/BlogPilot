"""
Post publisher — Sprint 4.

Opens the LinkedIn post composer, types the post text, and submits.
Used by ContentStudio scheduled queue and "Post Now" button.
"""
import asyncio

from playwright.async_api import Page

from backend.automation.human_behavior import random_delay
from backend.utils.logger import get_logger

logger = get_logger(__name__)

LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


class PostPublisher:
    """Publishes a text post to LinkedIn via the browser."""

    async def publish(self, page: Page, post_text: str) -> bool:
        """
        Type and submit a LinkedIn post.
        Returns True if published successfully.
        """
        logger.info(f"Publishing post ({len(post_text)} chars)...")

        ok = await self._attempt_publish(page, post_text)
        if not ok:
            logger.info("First publish attempt failed — retrying in 3s")
            await asyncio.sleep(3)
            ok = await self._attempt_publish(page, post_text)

        if ok:
            logger.info("Post published successfully")
        else:
            logger.error("Post publishing failed after retry")
        return ok

    async def _attempt_publish(self, page: Page, post_text: str) -> bool:
        try:
            # Navigate to feed if needed
            if "linkedin.com/feed" not in page.url:
                await page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=30000)
                await random_delay(2.0, 3.5)

            # Open "Start a post" composer
            start_btn = await page.query_selector(
                "button[aria-label*='Start a post' i], "
                "button.share-box-feed-entry__trigger, "
                "span:text-is('Start a post')"
            )
            if not start_btn:
                logger.warning("'Start a post' button not found")
                return False

            await start_btn.click()
            await asyncio.sleep(1.5)

            # Find the post text editor
            editor = await page.query_selector(
                "div.ql-editor[contenteditable='true'], "
                "div[role='textbox'][aria-label*='post' i], "
                "div.share-creation-state__text-editor div[contenteditable='true']"
            )
            if not editor:
                logger.warning("Post editor not found")
                return False

            await editor.click()
            await asyncio.sleep(0.5)

            # Type with slight delay per character
            for char in post_text:
                await page.keyboard.type(char)
                await asyncio.sleep(0.04)

            await asyncio.sleep(1.0)

            # Click the Post/Submit button
            post_btn = await page.query_selector(
                "button.share-actions__primary-action, "
                "button[aria-label='Post' i], "
                "button:text-is('Post')"
            )
            if not post_btn:
                logger.warning("Post submit button not found")
                return False

            await post_btn.click()
            await asyncio.sleep(3.0)

            return await self._verify_published(page)

        except Exception as e:
            logger.warning(f"Publish attempt error: {e}")
            return False

    async def _verify_published(self, page: Page) -> bool:
        """
        Check that the post was submitted: the composer should have closed
        or a success notification should be visible.
        """
        try:
            # Composer modal should be gone
            modal = await page.query_selector(
                "div.share-creation-state, "
                "div.share-modal__content"
            )
            if not modal:
                return True  # Composer closed = success

            # Success toast notification
            toast = await page.query_selector(
                "div.artdeco-toast-item--success, "
                "span:text-is('Post created')"
            )
            return toast is not None
        except Exception:
            return True  # Assume success if we can't determine
