"""
DOM email scraper — Sprint 6.

Extracts email from an already-open LinkedIn profile page by opening
the "Contact info" modal. Only works for 1st-degree connections.
"""
import re
from typing import Optional

from playwright.async_api import Page

from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def scrape(page: Page) -> Optional[str]:
    """
    Extract email from the contact info modal on a currently open LinkedIn profile.

    The profile page must already be loaded — this function does NOT navigate.
    Returns the email string if found, None otherwise. Never raises.
    """
    try:
        # Find "Contact info" link
        contact_link = await page.query_selector(
            "a#top-card-text-details-contact-info, "
            "a[href*='/overlay/contact-info/']"
        )
        if not contact_link:
            logger.debug("DOM scraper: no 'Contact info' link found")
            return None

        await contact_link.click()

        # Wait for modal to appear (max 3s)
        try:
            await page.wait_for_selector(
                "div.artdeco-modal, div[role='dialog']",
                timeout=3000,
            )
        except Exception:
            logger.debug("DOM scraper: contact info modal did not appear")
            await _close_modal(page)
            return None

        # Method 1: Look for mailto: href (most reliable)
        email_el = await page.query_selector("a[href^='mailto:']")
        if email_el:
            href = await email_el.get_attribute("href") or ""
            email = href.replace("mailto:", "").strip()
            if "@" in email:
                await _close_modal(page)
                logger.info(f"DOM scraper: email found via mailto — {email}")
                return email

        # Method 2: Scan text content for @ pattern
        spans = await page.query_selector_all(
            "div.pv-contact-info__ci-container span, "
            "section.pv-contact-info__contact-type span, "
            "div[role='dialog'] span, "
            "div[role='dialog'] a"
        )
        for span in spans:
            try:
                text = (await span.inner_text()).strip()
                if re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
                    await _close_modal(page)
                    logger.info(f"DOM scraper: email found via text match — {text}")
                    return text
            except Exception:
                continue

        await _close_modal(page)
        logger.debug("DOM scraper: no email found in contact info modal")
        return None

    except Exception as e:
        logger.warning(f"DOM scraper: unexpected error — {e}")
        try:
            await _close_modal(page)
        except Exception:
            pass
        return None


async def _close_modal(page: Page) -> None:
    """Close the contact info modal via dismiss button or Escape key."""
    try:
        close_btn = await page.query_selector(
            "button[aria-label='Dismiss'], "
            "button.artdeco-modal__dismiss"
        )
        if close_btn:
            await close_btn.click()
            await page.wait_for_timeout(300)
        else:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
    except Exception:
        pass
