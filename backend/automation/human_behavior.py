"""
Human behaviour simulation — Sprint 4.

All timing values come from config/settings.yaml (delays.*).
Used by every automation module to mimic realistic human interaction patterns.
"""
import asyncio
import random

from playwright.async_api import Page

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def random_delay(min_s: float, max_s: float) -> None:
    """
    Sleep for a gaussian-distributed random duration in [min_s, max_s].
    Gaussian distribution is more realistic than uniform (avoids perfectly
    random pauses that detection systems can flag).
    """
    mean = (min_s + max_s) / 2.0
    std = (max_s - min_s) / 6.0  # 3-sigma rule: 99.7% within [min, max]
    duration = random.gauss(mean, std)
    duration = max(min_s, min(max_s, duration))
    await asyncio.sleep(duration)


async def type_slowly(page: Page, selector: str, text: str) -> None:
    """
    Type text into a selector at a human-like WPM speed.
    WPM range from config: delays.typing_speed_wpm_min / max.
    Occasionally inserts a longer "thinking" pause.
    """
    wpm_min = float(cfg_get("delays.typing_speed_wpm_min", 35))
    wpm_max = float(cfg_get("delays.typing_speed_wpm_max", 65))
    wpm = random.uniform(wpm_min, wpm_max)

    # Average English word ≈ 5 chars  →  chars per second
    chars_per_sec = (wpm * 5.0) / 60.0
    base_delay = 1.0 / chars_per_sec  # seconds per character

    await page.click(selector)
    await asyncio.sleep(random.uniform(0.2, 0.5))

    for char in text:
        await page.keyboard.type(char)
        if random.random() < 0.03:
            # 3 % chance of a brief "thinking" pause
            await asyncio.sleep(random.uniform(0.4, 1.2))
        else:
            jitter = random.gauss(base_delay, base_delay * 0.3)
            await asyncio.sleep(max(0.02, jitter))


async def scroll_down(page: Page, passes: int = 3) -> None:
    """
    Scroll the page down `passes` times with random pauses.
    Simulates a human reading and scrolling through a feed.
    """
    for i in range(passes):
        # Random scroll distance in pixels
        distance = random.randint(300, 900)
        await page.evaluate(f"window.scrollBy(0, {distance})")
        await random_delay(1.5, 4.0)
        logger.debug(f"Scroll pass {i + 1}/{passes}")


async def hover_before_click(page: Page, selector: str) -> None:
    """
    Hover over an element for a human-like duration before clicking.
    Safer than direct click — avoids bot detection on interactive elements.
    """
    element = await page.query_selector(selector)
    if element:
        await element.hover()
        await random_delay(0.3, 1.2)
        await element.click()
    else:
        logger.warning(f"hover_before_click: element not found: {selector}")


async def mouse_move_to(page: Page, selector: str) -> None:
    """Move mouse to an element without clicking (natural cursor movement)."""
    element = await page.query_selector(selector)
    if element:
        box = await element.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
            y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)
            await page.mouse.move(x, y)
