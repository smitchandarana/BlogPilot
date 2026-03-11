"""
Hunter.io client — Sprint 6.

Optional email finder using the Hunter.io API.
Only runs when use_hunter_api=True AND a valid API key is configured.
Never raises — always returns str | None.
"""
import json
import os
from typing import Optional

import httpx

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def find(first_name: str, last_name: str, domain: str) -> Optional[str]:
    """
    Find an email address using the Hunter.io email-finder API.

    Returns the email if found with confidence >= 70, else None.
    Returns None immediately if Hunter is disabled or no API key.
    Never raises.
    """
    # Guard: check config flag
    if not cfg_get("email_enrichment.use_hunter_api", False):
        return None

    # Guard: resolve API key
    api_key = _get_hunter_key()
    if not api_key:
        logger.debug("Hunter: no API key configured — skipping")
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/email-finder",
                params={
                    "first_name": first_name,
                    "last_name": last_name,
                    "domain": domain,
                    "api_key": api_key,
                },
            )

        if resp.status_code == 401:
            logger.warning("Hunter: API key invalid (401)")
            return None

        if resp.status_code == 429:
            logger.warning("Hunter: rate limit hit (429)")
            return None

        if resp.status_code != 200:
            logger.warning(f"Hunter: unexpected status {resp.status_code}")
            return None

        data = resp.json().get("data", {})
        email = data.get("email")
        confidence = data.get("confidence", 0)

        if email and confidence >= 70:
            logger.info(f"Hunter: found {email} (confidence={confidence})")
            return email

        logger.debug(f"Hunter: low confidence ({confidence}) for {first_name} {last_name} @ {domain}")
        return None

    except Exception as e:
        logger.warning(f"Hunter: request failed — {e}")
        return None


def _get_hunter_key() -> str:
    """
    Resolve Hunter API key from env var or encrypted secrets file.
    """
    key = os.environ.get("HUNTER_API_KEY", "")
    if key:
        return key

    secrets_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets", "hunter.json")
    )
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r") as f:
                data = json.load(f)
            return data.get("api_key", "")
        except Exception as e:
            logger.warning(f"Hunter: failed to read secrets file — {e}")

    return ""
