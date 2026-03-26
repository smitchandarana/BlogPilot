"""
LinkedIn authentication — Sprint 4.

Cookie-first login with credential fallback.
Credentials stored encrypted in config/.secrets/linkedin.json.
Session persists via Playwright's persistent context (user data dir).
"""
import json
import os
from typing import Optional

from playwright.async_api import Page

from backend.utils.encryption import encrypt, decrypt
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SECRETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets")
)
_CREDS_FILE = os.path.join(_SECRETS_DIR, "linkedin.json")

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


# ── Credential helpers ─────────────────────────────────────────────────────

def load_credentials() -> tuple[str, str]:
    """Load and decrypt LinkedIn credentials from config/.secrets/linkedin.json."""
    if not os.path.exists(_CREDS_FILE):
        raise FileNotFoundError(
            f"LinkedIn credentials not found at {_CREDS_FILE}.\n"
            "Run:  python -m backend.utils.setup_credentials"
        )
    with open(_CREDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    email = decrypt(data["email"])
    password = decrypt(data["password"])
    return email, password


def save_credentials(email: str, password: str) -> None:
    """Encrypt and save LinkedIn credentials."""
    os.makedirs(_SECRETS_DIR, exist_ok=True)
    data = {
        "email": encrypt(email),
        "password": encrypt(password),
    }
    fd = os.open(_CREDS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, json.dumps(data).encode("utf-8"))
    finally:
        os.close(fd)
    logger.info(f"LinkedIn credentials saved (encrypted) → {_CREDS_FILE}")


def credentials_exist() -> bool:
    """Return True if encrypted credentials file exists."""
    return os.path.exists(_CREDS_FILE)


# ── Login handler ──────────────────────────────────────────────────────────

class LinkedInLogin:
    """
    Manages LinkedIn authentication.
    Strategy: check if already logged in → skip.
    Otherwise try credential login and persist session via browser profile.
    """

    async def login(
        self,
        page: Page,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """
        Full login flow. Returns True if logged in.
        Uses stored credentials if email/password not provided.
        """
        # Already logged in?
        await page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        if await self.is_logged_in(page):
            logger.info("Already logged in via persistent session")
            return True

        logger.info("Not logged in — starting credential login")

        # Load credentials if not provided
        if email is None or password is None:
            email, password = load_credentials()

        return await self._credential_login(page, email, password)

    async def _credential_login(self, page: Page, email: str, password: str) -> bool:
        """Fill login form and submit."""
        try:
            await page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Dismiss cookie consent dialog if present (EU/GDPR)
            await self._dismiss_cookie_consent(page)

            # Check for security challenge on the login page itself
            challenged = await self.handle_security_challenge(page)
            if challenged:
                return False

            # Wait for the login form — try multiple selectors for resilience
            email_selector = await self._find_email_field(page, timeout=15000)
            if email_selector is None:
                logger.warning(f"Login form not found (current URL: {page.url}) — LinkedIn may be showing a challenge page")
                challenged = await self.handle_security_challenge(page)
                if challenged:
                    return False
                # Try navigating directly to the login URL once more
                await page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                await self._dismiss_cookie_consent(page)
                email_selector = await self._find_email_field(page, timeout=10000)
                if email_selector is None:
                    logger.error(f"Login form still not found after retry (URL: {page.url}) — aborting")
                    return False

            # Fill email
            await page.fill(email_selector, email)
            await page.wait_for_timeout(600)

            # Fill password
            password_selector = await self._find_password_field(page)
            await page.fill(password_selector, password)
            await page.wait_for_timeout(500)

            # Submit
            await page.click('[data-litms-control-urn="login-submit"]')
            await page.wait_for_timeout(4000)

            # Check for security challenge
            challenged = await self.handle_security_challenge(page)
            if challenged:
                # Challenge detected — engine paused, user must intervene
                return False

            if await self.is_logged_in(page):
                logger.info("Credential login successful — session saved to browser profile")
                return True

            logger.error("Credential login failed — incorrect credentials or LinkedIn blocked login")
            return False

        except Exception as e:
            logger.error(f"Credential login error: {e}")
            return False

    async def _dismiss_cookie_consent(self, page: Page) -> None:
        """Click the cookie accept button if LinkedIn shows a consent dialog."""
        consent_selectors = [
            "button[action-type='ACCEPT']",           # LinkedIn GDPR banner
            "button[data-tracking-control-name='ga-cookie-banner-accept']",
            "button.artdeco-button--primary[data-test-modal-close-btn]",
            "button:has-text('Accept')",
            "button:has-text('Accept all')",
            "button:has-text('Allow all cookies')",
            "button:has-text('Agree')",
        ]
        for sel in consent_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.info(f"Cookie consent dismissed (selector: {sel})")
                    await page.wait_for_timeout(1000)
                    return
            except Exception:
                continue

    async def _find_email_field(self, page: Page, timeout: int = 15000) -> str | None:
        """Return the CSS selector for the email input, or None if not found."""
        candidates = [
            "#username",
            "input[name='session_key']",
            "input[autocomplete='username']",
            "input[type='email']",
        ]
        # Wait for any of the candidates to appear
        try:
            await page.wait_for_selector(
                ", ".join(candidates), timeout=timeout
            )
        except Exception:
            return None
        for sel in candidates:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return sel
        return None

    async def _find_password_field(self, page: Page) -> str:
        """Return the CSS selector for the password input."""
        candidates = [
            "#password",
            "input[name='session_password']",
            "input[type='password']",
        ]
        for sel in candidates:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return sel
        return "#password"  # fallback

    async def is_logged_in(self, page: Page) -> bool:
        """Check if currently logged into LinkedIn."""
        try:
            url = page.url
            # Definitive "not logged in" signals — LinkedIn redirects here when unauthenticated
            if any(x in url for x in [
                "linkedin.com/login",
                "linkedin.com/checkpoint",
                "linkedin.com/uas/",
                "linkedin.com/authwall",
                "linkedin.com/signup",
            ]):
                return False
            # If we're on any authenticated page, we're logged in
            # LinkedIn always redirects unauthenticated users away from these paths
            if any(x in url for x in [
                "linkedin.com/feed",
                "linkedin.com/mynetwork",
                "linkedin.com/jobs",
                "linkedin.com/messaging",
                "linkedin.com/notifications",
                "linkedin.com/in/",
            ]):
                return True
            # Fallback: try DOM selectors (LinkedIn may update class names)
            nav = await page.query_selector(
                "#global-nav, "
                "div.global-nav__content, "
                "nav[aria-label='Global navigation'], "
                "header.global-nav, "
                "[data-test-id='nav-logo'], "
                "img[alt='LinkedIn']"
            )
            return nav is not None
        except Exception:
            return False

    async def detect_reauth_needed(self, page: Page) -> bool:
        """Return True if LinkedIn is redirecting to a login/auth page."""
        try:
            url = page.url
            return any(x in url for x in [
                "linkedin.com/login",
                "linkedin.com/checkpoint",
                "linkedin.com/uas/login",
            ])
        except Exception:
            return False

    async def handle_security_challenge(self, page: Page) -> bool:
        """
        Detect CAPTCHA or email verification.
        If found: broadcast alert, then WAIT up to 120s for the user to
        complete the challenge manually in the visible browser window.
        Returns True if a challenge was detected (action blocked).
        Returns False if the user resolved it in time.
        """
        try:
            url = page.url
            challenge_detected = False

            # URL-based detection
            if any(x in url for x in ["checkpoint/challenge", "checkpoint/lg", "security-verification"]):
                logger.error(f"LinkedIn security challenge at: {url}")
                challenge_detected = True

            # DOM-based CAPTCHA detection
            if not challenge_detected:
                captcha_selectors = [
                    "iframe[src*='recaptcha']",
                    "div[class*='captcha']",
                    "#captcha-internal",
                    "div[id*='challenge']",
                ]
                for sel in captcha_selectors:
                    el = await page.query_selector(sel)
                    if el:
                        logger.error(f"CAPTCHA detected (selector: {sel})")
                        challenge_detected = True
                        break

            if not challenge_detected:
                return False

            # Alert the user — they need to complete the challenge in the browser
            try:
                from backend.api.websocket import schedule_broadcast
                schedule_broadcast("alert", {
                    "level": "warning",
                    "message": "LinkedIn security challenge detected — please complete it in the browser window. Waiting up to 120 seconds…",
                })
            except Exception:
                pass

            # Wait up to 120s for the user to complete the challenge
            logger.info("Waiting up to 120s for user to complete security challenge…")
            for i in range(24):  # 24 x 5s = 120s
                await page.wait_for_timeout(5000)

                # Check if we're past the challenge (redirected to feed or similar)
                current_url = page.url
                if not any(x in current_url for x in [
                    "checkpoint/challenge", "checkpoint/lg", "security-verification",
                    "checkpoint/challengesV2",
                ]):
                    # User completed the challenge
                    await page.wait_for_timeout(2000)
                    if await self.is_logged_in(page):
                        logger.info("Security challenge resolved — login successful!")
                        try:
                            from backend.api.websocket import schedule_broadcast
                            schedule_broadcast("alert", {
                                "level": "info",
                                "message": "Security challenge resolved. Engine resuming.",
                            })
                        except Exception:
                            pass
                        return False  # Challenge resolved, login OK

                if (i + 1) % 6 == 0:
                    logger.info(f"Still waiting for challenge resolution… ({(i+1)*5}s elapsed)")

            # Timeout — user didn't complete in time
            logger.error("Security challenge not resolved within 120s — aborting")
            self._pause_and_alert("security_challenge")
            return True

        except Exception as e:
            logger.warning(f"Security challenge detection error: {e}")

        return False

    def _pause_and_alert(self, reason: str) -> None:
        """Record circuit breaker error (which triggers pause) and broadcast UI alert."""
        msg = (
            "CAPTCHA detected — manual intervention required."
            if reason == "captcha"
            else f"LinkedIn security challenge ({reason}) — please resolve in browser."
        )

        try:
            from backend.api.websocket import schedule_broadcast
            schedule_broadcast("alert", {"level": "critical", "message": msg})
        except Exception as e:
            logger.warning(f"Alert broadcast failed: {e}")

        try:
            from backend.core.engine import get_engine
            engine = get_engine()
            if engine:
                engine.circuit_breaker.record_error(reason)
        except Exception as e:
            logger.warning(f"Circuit breaker record failed: {e}")
