"""
BrowserManager — Sprint 4.

Creates and manages a Playwright browser session for one pipeline run.
NOT a singleton: instantiate per pipeline run, close when done.
Uses launch_persistent_context so LinkedIn session cookies survive across runs.
"""
import os
import threading
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# BUG FIX: Serialize concurrent launch() calls so two workers never try to
# open the same persistent profile directory simultaneously (Chromium locks it).
_BROWSER_LAUNCH_LOCK = threading.Lock()


class BrowserManager:
    """
    Async Playwright browser session manager.
    Wraps a persistent browser context with stealth settings.

    Usage:
        browser = BrowserManager()
        await browser.launch()
        page = await browser.get_page()
        # ... do work ...
        await browser.close()
    """

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def launch(self) -> None:
        """Launch Playwright with stealth settings and persistent profile."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        # BUG FIX: Hold the module-level lock while launching so that a
        # concurrent worker (e.g. approval + feed scan) cannot attempt to open
        # the same profile directory at the same time.  The lock is released
        # after launch_persistent_context() returns, not at browser.close().
        with _BROWSER_LAUNCH_LOCK:
            await self._do_launch()

    async def _do_launch(self) -> None:
        """Internal: perform the actual Playwright launch (called under lock)."""
        headless = bool(cfg_get("browser.headless", False))
        profile_path = cfg_get("browser.profile_path", "./browser_profile")
        viewport_width = int(cfg_get("browser.viewport_width", 1366))
        viewport_height = int(cfg_get("browser.viewport_height", 768))
        slow_mo = int(cfg_get("browser.slow_mo_ms", 80))

        # Resolve relative path
        if not os.path.isabs(profile_path):
            profile_path = os.path.abspath(profile_path)
        os.makedirs(profile_path, exist_ok=True)

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--start-maximized",
        ]

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=headless,
            args=launch_args,
            viewport={"width": viewport_width, "height": viewport_height},
            slow_mo=slow_mo,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Stealth: hide webdriver fingerprint
        await self._context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}};
            """
        )

        # Use existing page or open a new one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        logger.info(
            f"Browser launched (headless={headless}, profile={profile_path})"
        )

    async def get_page(self) -> Page:
        """Return the current page, launching browser if needed."""
        if self._context is None or self._page is None:
            await self.launch()
        return self._page

    async def new_page(self) -> Page:
        """Open a new tab in the current context."""
        if self._context is None:
            await self.launch()
        self._page = await self._context.new_page()
        return self._page

    async def close(self) -> None:
        """Close browser context and stop Playwright."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
                self._page = None
        except Exception as e:
            logger.warning(f"Browser context close error: {e}")

        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception as e:
            logger.warning(f"Playwright stop error: {e}")

        logger.info("Browser closed")

    def is_running(self) -> bool:
        """True if browser context is active."""
        return self._playwright is not None and self._context is not None
