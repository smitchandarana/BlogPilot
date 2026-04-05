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

    def __init__(self, leads_store=None, broadcast_fn=None):
        self._leads_store = leads_store
        self._broadcast_fn = broadcast_fn or (lambda event, payload: None)

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

        if db is not None and self._leads_store is not None:
            try:
                self._leads_store.create_lead(data, db)

                # Broadcast to UI
                try:
                    self._broadcast_fn("lead_added", {
                        "name": f"{data['first_name'] or ''} {data['last_name'] or ''}".strip(),
                        "company": data["company"] or "",
                        "email": data["email"],
                    })
                except Exception as bc_exc:
                    logger.debug(f"Lead broadcast error: {bc_exc}")
            except Exception as e:
                logger.warning(f"Lead save error: {e}")

        return data

    # ── Field extractors ────────────────────────────────────────────────────

    async def _extract_name(self, page: Page) -> Optional[str]:
        # Try CSS selectors first (ordered by reliability)
        for sel in [
            "h1.text-heading-xlarge",
            "h1[class*='text-heading-xlarge']",
            "section.artdeco-card h1",
            "main h1",
            "div[class*='ph5'] h1",
            "section.pv-top-card h1",
            "h1",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip().split("\n")[0].strip()
                if text and 2 < len(text) < 80:
                    return text

        # JS fallback — find the first h1 in main content
        try:
            name = await page.evaluate("""() => {
                const h1s = Array.from(document.querySelectorAll('h1'));
                for (const h of h1s) {
                    const t = h.innerText.trim().split('\\n')[0].trim();
                    if (t.length > 2 && t.length < 80) return t;
                }
                return null;
            }""")
            if name:
                return name
        except Exception:
            pass
        return None

    async def _extract_title(self, page: Page) -> Optional[str]:
        for sel in [
            "div.text-body-medium.break-words",
            "div[class*='text-body-medium'][class*='break-words']",
            "div[class*='pv-text-details__left-panel'] div.text-body-medium",
            "section.pv-top-card div.text-body-medium",
            "div[class*='ph5'] div.text-body-medium",
            "div[class*='pv-text-details'] .text-body-medium",
            "[data-generated-suggestion-target]",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip().split("\n")[0].strip()
                if text and 3 < len(text) < 300:
                    return text

        # JS fallback — headline is the element right after h1 in the top card
        try:
            title = await page.evaluate("""() => {
                const h1 = document.querySelector('h1');
                if (!h1) return null;
                let el = h1.nextElementSibling;
                while (el) {
                    const t = el.innerText.trim().split('\\n')[0].trim();
                    if (t.length > 3 && t.length < 300) return t;
                    el = el.nextElementSibling;
                }
                return null;
            }""")
            if title:
                return title
        except Exception:
            pass
        return None

    async def _extract_company(self, page: Page) -> Optional[str]:
        # Strategy 1: aria-label based
        for sel in [
            "button[aria-label*='Current company' i] span",
            "span[aria-label*='Current company' i]",
            "a[aria-label*='Current company' i] span",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    return text

        # Strategy 2: experience section / company links in top card
        for sel in [
            "section[id*='experience'] li:first-child a[href*='/company/'] span[aria-hidden='true']",
            "div[class*='pv-text-details__right-panel'] a[href*='/company/'] span",
            "section.pv-top-card a[href*='/company/'] span",
            "a[href*='/company/'] div[class*='t-14']",
            "li.pv-text-details__right-panel-item span.t-14",
            "section[id*='experience'] li:first-child span.t-14.t-normal",
        ]:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip().split("\n")[0].strip()
                if text:
                    return text

        # Strategy 3: JS fallback — find first company link in top area
        try:
            company = await page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a[href*="/company/"]'));
                for (const a of links) {
                    const t = a.innerText.trim().split('\\n')[0].trim();
                    if (t.length > 0 && t.length < 100) return t;
                }
                return null;
            }""")
            if company:
                return company
        except Exception:
            pass
        return None

    async def _extract_degree(self, page: Page) -> Optional[int]:
        """Return 1, 2, or 3 for connection degree; None if unknown."""
        try:
            for sel in [
                "span.dist-value",
                "span[class*='distance-badge'] span[aria-hidden='true']",
                "span[class*='distance-badge']",
                "span[class*='connection-degree-badge']",
                "span.pvs-header__subtitle span[aria-hidden='true']",
                "[class*='degree-badge']",
            ]:
                el = await page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    match = re.search(r"(\d)", text)
                    if match:
                        return int(match.group(1))

            # Fallback: search full page text for degree badge patterns
            body_text = await page.text_content("body") or ""
            degree_match = re.search(r"(\d)(?:st|nd|rd)\s*[-•]\s*degree", body_text, re.IGNORECASE)
            if degree_match:
                return int(degree_match.group(1))

            # JS fallback
            degree = await page.evaluate("""() => {
                const spans = Array.from(document.querySelectorAll('span'));
                for (const s of spans) {
                    const t = s.innerText.trim();
                    const m = t.match(/^([123])(?:st|nd|rd)[\\s\\-•]*degree/i);
                    if (m) return parseInt(m[1]);
                }
                return null;
            }""")
            if degree:
                return degree
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
