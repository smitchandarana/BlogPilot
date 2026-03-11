"""
Email enricher — Sprint 6.

Orchestrates all email enrichment methods in priority order:
  1. DOM scraper (1st-degree connections only)
  2. Hunter.io API (optional, key-gated)
  3. Pattern generator + SMTP verifier

Stops at the first successful method.
"""
from typing import Optional

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EmailEnricher:
    """
    Orchestrates email enrichment across multiple methods.
    Dependencies are injected — no global imports of automation modules.
    """

    def __init__(self, page=None):
        """
        Args:
            page: Playwright Page object (needed for DOM scraper).
                  Can be None if only pattern/SMTP methods are desired.
        """
        self._page = page

    async def enrich(self, profile_data: dict) -> dict:
        """
        Attempt to find and verify an email for the given profile.

        Args:
            profile_data: dict with keys:
                first_name, last_name, company_domain, connection_degree,
                linkedin_url (used for DB update)

        Returns:
            {email: str|None, status: "NOT_FOUND"|"FOUND"|"VERIFIED", method: str|None}
        """
        first_name = profile_data.get("first_name", "") or ""
        last_name = profile_data.get("last_name", "") or ""
        domain = profile_data.get("company_domain", "") or ""
        degree = profile_data.get("connection_degree")
        linkedin_url = profile_data.get("linkedin_url", "")

        result = {"email": None, "status": "NOT_FOUND", "method": None}

        # Method 1: DOM scraper (1st-degree only)
        if (
            self._page
            and degree == 1
            and cfg_get("email_enrichment.use_dom_scraper", True)
        ):
            try:
                from backend.enrichment import dom_email_scraper

                email = await dom_email_scraper.scrape(self._page)
                if email:
                    result = {"email": email, "status": "FOUND", "method": "DOM"}
                    logger.info(f"Enricher: email found via DOM — {email}")
                    await self._finalize(linkedin_url, result)
                    return result
            except Exception as e:
                logger.warning(f"Enricher: DOM scraper error — {e}")

        # Method 2: Hunter.io API
        if domain and cfg_get("email_enrichment.use_hunter_api", False):
            try:
                from backend.enrichment import hunter_client

                email = await hunter_client.find(first_name, last_name, domain)
                if email:
                    result = {"email": email, "status": "FOUND", "method": "HUNTER"}
                    logger.info(f"Enricher: email found via Hunter — {email}")
                    await self._finalize(linkedin_url, result)
                    return result
            except Exception as e:
                logger.warning(f"Enricher: Hunter error — {e}")

        # Method 3: Pattern generator + SMTP verifier
        if (
            domain
            and first_name
            and last_name
            and cfg_get("email_enrichment.use_pattern_generator", True)
        ):
            try:
                from backend.enrichment import pattern_generator, smtp_verifier

                candidates = pattern_generator.generate(first_name, last_name, domain)
                max_attempts = int(
                    cfg_get("email_enrichment.max_pattern_attempts", 5)
                )

                for candidate in candidates[:max_attempts]:
                    verified = await smtp_verifier.verify(candidate)
                    if verified:
                        result = {
                            "email": candidate,
                            "status": "VERIFIED",
                            "method": "PATTERN_SMTP",
                        }
                        logger.info(
                            f"Enricher: email verified via SMTP — {candidate}"
                        )
                        await self._finalize(linkedin_url, result)
                        return result
            except Exception as e:
                logger.warning(f"Enricher: pattern/SMTP error — {e}")

        # Fallback: no email found
        logger.info(
            f"Enricher: no email found for {first_name} {last_name} @ {domain}"
        )
        await self._finalize(linkedin_url, result)
        return result

    async def _finalize(self, linkedin_url: str, result: dict) -> None:
        """Update DB and broadcast WebSocket event."""
        if not linkedin_url:
            return

        # Update lead in DB
        try:
            import hashlib
            from backend.storage.database import get_db
            from backend.storage import leads_store

            lead_id = hashlib.sha256(linkedin_url.encode()).hexdigest()
            with get_db() as db:
                leads_store.update_email(
                    lead_id,
                    result.get("email") or "",
                    result["status"],
                    result.get("method") or "",
                    db,
                )
        except Exception as e:
            logger.warning(f"Enricher: DB update failed — {e}")

        # Broadcast to UI
        try:
            from backend.api.websocket import schedule_broadcast

            schedule_broadcast("lead_updated", {
                "linkedin_url": linkedin_url,
                "email": result.get("email"),
                "status": result["status"],
                "method": result.get("method"),
            })
        except Exception:
            pass
