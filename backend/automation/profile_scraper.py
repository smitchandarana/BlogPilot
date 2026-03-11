"""
Profile scraper — Sprint 4.

Visits a LinkedIn profile page and extracts: name, title, company, degree,
and (for 1st-degree connections) email from the contact info modal.
Saves the result to the leads table.
"""
import re
from typing import Optional

from playwright.async_api import Page

from backend.automation.human_behavior import random_delay
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ProfileScraper:
    """
    Scrapes structured data from a LinkedIn profile page.
    Saves a Lead record to the database if db is provided.
    """

    async def scrape(self, page: Page, profile_url: str, db=None) -> dict:
        """
        Navigate to profile_url, extract all available fields, and return a dict.
        Also saves lead to DB and broadcasts lead_added WebSocket event.
        """
        logger.info(f"Scraping profile: {profile_url}")

        await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        await random_delay(1.5, 3.0)

        data: dict = {
            "linkedin_url": profile_url,
            "first_name": None,
            "last_name": None,
            "title": None,
            "company": None,
            "company_domain": None,
            "email": None,
            "connection_degree": None,
            "source": "feed_engagement",
        }

        # Name
        full_name = await self._extract_name(page)
        if full_name:
            parts = full_name.strip().split(" ", 1)
            data["first_name"] = parts[0]
            data["last_name"] = parts[1] if len(parts) > 1 else ""

        # Title
        data["title"] = await self._extract_title(page)

        # Company
        data["company"] = await self._extract_company(page)
        if data["company"]:
            data["company_domain"] = self._infer_domain(data["company"])

        # Connection degree
        data["connection_degree"] = await self._extract_degree(page)

        # Email — only visible for 1st-degree connections
        if data["connection_degree"] == 1:
            data["email"] = await self._extract_email(page)

        logger.info(
            f"Profile scraped: {data['first_name']} {data['last_name']} "
            f"@ {data['company']} (degree={data['connection_degree']})"
        )

        if db is not None:
            try:
                from backend.storage import leads_store
                leads_store.create_lead(data, db)

                # Broadcast to UI
                try:
                    from backend.api.websocket import schedule_broadcast
                    schedule_broadcast("lead_added", {
                        "name": f"{data['first_name'] or ''} {data['last_name'] or ''}".strip(),
                        "company": data["company"] or "",
                        "email": data["email"],
                    })
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Lead save error: {e}")

        return data

    # ── Field extractors ────────────────────────────────────────────────────

    async def _extract_name(self, page: Page) -> Optional[str]:
        for sel in [
            "h1.text-heading-xlarge",
            "h1[class*='inline t-24']",
            "h1",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text and len(text) < 100:
                    return text
        return None

    async def _extract_title(self, page: Page) -> Optional[str]:
        for sel in [
            "div.text-body-medium.break-words",
            "div[class*='text-body-medium']",
            "div.ph5 .text-body-medium",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text and len(text) < 300:
                    return text
        return None

    async def _extract_company(self, page: Page) -> Optional[str]:
        for sel in [
            "button[aria-label*='Current company' i] span",
            "span[aria-label*='Current company' i]",
            "li.pv-text-details__right-panel-item span.t-14",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    return text
        return None

    async def _extract_degree(self, page: Page) -> Optional[int]:
        """Return 1, 2, or 3 for connection degree; None if unknown."""
        try:
            el = await page.query_selector(
                "span.dist-value, "
                "span[class*='distance-badge'] span[aria-hidden='true']"
            )
            if el:
                text = (await el.inner_text()).strip()
                match = re.search(r"(\d)", text)
                if match:
                    return int(match.group(1))
        except Exception as e:
            logger.debug(f"Degree extraction error: {e}")
        return None

    async def _extract_email(self, page: Page) -> Optional[str]:
        """
        Click the 'Contact info' link to open the modal and look for a mailto link.
        Only available for 1st-degree connections.
        """
        try:
            contact_link = await page.query_selector(
                "a#top-card-text-details-contact-info, "
                "a[href*='/overlay/contact-info/']"
            )
            if not contact_link:
                return None

            await contact_link.click()
            await page.wait_for_timeout(1500)

            # Explicit mailto href (most reliable)
            email_el = await page.query_selector("a[href^='mailto:']")
            if email_el:
                href = await email_el.get_attribute("href") or ""
                email = href.replace("mailto:", "").strip()
                if "@" in email:
                    await self._close_modal(page)
                    logger.info(f"Email found: {email}")
                    return email

            # Fallback: scan span text for email pattern
            spans = await page.query_selector_all(
                "div.pv-contact-info__ci-container span, "
                "section.pv-contact-info__contact-type span"
            )
            for span in spans:
                text = (await span.inner_text()).strip()
                if re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", text):
                    await self._close_modal(page)
                    logger.info(f"Email found (text match): {text}")
                    return text

            await self._close_modal(page)
        except Exception as e:
            logger.debug(f"Email extraction error: {e}")

        return None

    async def _close_modal(self, page: Page) -> None:
        try:
            close_btn = await page.query_selector(
                "button[aria-label='Dismiss'], "
                "button.artdeco-modal__dismiss"
            )
            if close_btn:
                await close_btn.click()
                await page.wait_for_timeout(500)
        except Exception:
            pass

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _infer_domain(self, company_name: str) -> str:
        """
        Derive a best-guess domain from a company name.
        e.g. "Acme Corp Ltd" → "acmecorp.com"
        This is used only as a starting point for SMTP pattern generation.
        """
        if not company_name:
            return ""
        domain = company_name.lower()
        for suffix in [" inc", " ltd", " llc", " corp", " limited", " pvt", " co.", "."]:
            domain = domain.replace(suffix, "")
        domain = re.sub(r"[^a-z0-9]", "", domain)
        return f"{domain}.com" if domain else ""
