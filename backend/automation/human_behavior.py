"""
Human behaviour simulation — Sprint 4.

All timing values come from config/settings.yaml (delays.*).
Used by every automation module to mimic realistic human interaction patterns.

Enhanced with SessionProfile, typo injection, Bezier mouse movement,
rethink_comment, and session_start_delay.
"""
import asyncio
import math
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Page

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SkipSessionException(Exception):
    """Raised by session_start_delay() when the session should be skipped (8% chance)."""
    pass


# ---------------------------------------------------------------------------
# SessionProfile — generated once per engine session
# ---------------------------------------------------------------------------

@dataclass
class SessionProfile:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    wpm: int = field(default_factory=lambda: random.randint(55, 90))
    typo_rate: float = field(default_factory=lambda: random.uniform(0.02, 0.06))
    mouse_overshoot: float = field(default_factory=lambda: random.uniform(0.05, 0.18))
    scroll_speed: int = field(default_factory=lambda: random.randint(300, 800))
    pause_profile: str = field(
        default_factory=lambda: random.choice(["focused", "distracted", "slow"])
    )


_session_profile: Optional[SessionProfile] = None


def get_session_profile() -> SessionProfile:
    """Return the singleton SessionProfile, creating one if needed."""
    global _session_profile
    if _session_profile is None:
        _session_profile = SessionProfile()
        logger.info(
            f"New session profile: id={_session_profile.session_id}, "
            f"wpm={_session_profile.wpm}, typo_rate={_session_profile.typo_rate:.3f}, "
            f"pause_profile={_session_profile.pause_profile}"
        )
    return _session_profile


def reset_session_profile() -> None:
    """Clear the singleton so a fresh profile is generated on next access."""
    global _session_profile
    _session_profile = None
    logger.info("Session profile reset")


# ---------------------------------------------------------------------------
# Bezier helpers (private)
# ---------------------------------------------------------------------------

def _bezier_point(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    """Evaluate a cubic Bezier curve at parameter t in [0, 1]."""
    u = 1.0 - t
    return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3


def _random_offset() -> float:
    """Random control-point offset +/-30 to 120px."""
    return random.uniform(30, 120) * random.choice([-1, 1])


def _generate_bezier_path(
    x0: float, y0: float, x1: float, y1: float, overshoot: float = 0.0
) -> list[tuple[float, float]]:
    """
    Generate a list of (x, y) points along a cubic Bezier curve from
    (x0, y0) to (x1, y1) with random control-point offsets and optional overshoot.
    """
    dx = x1 - x0
    dy = y1 - y0

    # Three random control points with offsets
    cp1x = x0 + dx * 0.25 + _random_offset()
    cp1y = y0 + dy * 0.25 + _random_offset()
    cp2x = x0 + dx * 0.75 + _random_offset()
    cp2y = y0 + dy * 0.75 + _random_offset()

    # Overshoot: extend final target past destination
    target_x = x1 + dx * overshoot * random.choice([-1, 1])
    target_y = y1 + dy * overshoot * random.choice([-1, 1])

    # Number of steps based on distance
    dist = math.hypot(dx, dy)
    step_px = random.randint(8, 20)
    num_steps = max(10, int(dist / step_px))

    points: list[tuple[float, float]] = []
    for i in range(num_steps + 1):
        t = i / num_steps
        px = _bezier_point(t, x0, cp1x, cp2x, target_x)
        py = _bezier_point(t, y0, cp1y, cp2y, target_y)
        # Micro-tremor +/-1 to 3px
        px += random.uniform(-3, 3)
        py += random.uniform(-3, 3)
        points.append((px, py))

    # If overshoot was applied, add correction points back to true target
    if overshoot > 0.01:
        correction_steps = random.randint(3, 6)
        last_x, last_y = points[-1]
        for i in range(1, correction_steps + 1):
            t = i / correction_steps
            cx = last_x + (x1 - last_x) * t + random.uniform(-2, 2)
            cy = last_y + (y1 - last_y) * t + random.uniform(-2, 2)
            points.append((cx, cy))

    return points


# ---------------------------------------------------------------------------
# Core functions — original signatures preserved
# ---------------------------------------------------------------------------

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

    Uses SessionProfile for base WPM. Includes:
    - Per-char jitter +/-10-60ms
    - Think pauses at punctuation (0.8-3.2s)
    - Pre-typing delay 2-8s (simulates reading)
    - Typo injection + backspace correction (based on profile.typo_rate)
    - Burst mode: every 8-20 chars, rapid-fire 3-5 chars with ~0 delay
    """
    profile = get_session_profile()

    # Derive base char delay from session WPM
    chars_per_sec = (profile.wpm * 5.0) / 60.0
    base_delay = 1.0 / chars_per_sec

    await page.click(selector)

    # Pre-typing delay: simulate reading the field / thinking
    pre_delay = random.uniform(2.0, 8.0)
    logger.debug(f"Pre-typing delay: {pre_delay:.1f}s")
    await asyncio.sleep(pre_delay)

    chars_since_burst = 0
    next_burst_at = random.randint(8, 20)
    burst_remaining = 0

    for char in text:
        # --- Burst mode: rapid-fire with ~0 delay ---
        if burst_remaining > 0:
            await page.keyboard.type(char)
            burst_remaining -= 1
            await asyncio.sleep(random.uniform(0.01, 0.03))
            continue

        if chars_since_burst >= next_burst_at:
            burst_remaining = random.randint(3, 5) - 1  # -1 because current char counts
            chars_since_burst = 0
            next_burst_at = random.randint(8, 20)
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.01, 0.03))
            continue

        # --- Typo injection ---
        if random.random() < profile.typo_rate:
            wrong_char = random.choice("asdfghjklqwertyuiopzxcvbnm")
            await page.keyboard.type(wrong_char)
            await asyncio.sleep(random.uniform(0.3, 1.2))
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.05, 0.15))

        # --- Type the actual character ---
        await page.keyboard.type(char)
        chars_since_burst += 1

        # --- Think pause at punctuation ---
        if char in ".!?,;:":
            await asyncio.sleep(random.uniform(0.8, 3.2))
        else:
            # Normal per-char delay with jitter +/-10-60ms
            jitter_ms = random.uniform(-60, 60)
            delay = base_delay + (jitter_ms / 1000.0)
            await asyncio.sleep(max(0.02, delay))


async def scroll_down(page: Page, passes: int = 3) -> None:
    """
    Scroll the page down `passes` times with human-like variation.

    Uses SessionProfile.scroll_speed. Mixes JS scrollBy and mouse.wheel.
    Includes scroll-back (25%), full-stop pauses (15%), and variable delays.
    """
    profile = get_session_profile()

    for i in range(passes):
        # 15% chance: full stop — hover in place without scrolling
        if random.random() < 0.15:
            stop_duration = random.uniform(3.0, 10.0)
            logger.debug(f"Scroll pass {i + 1}/{passes}: full stop {stop_duration:.1f}s")
            await asyncio.sleep(stop_duration)
            continue

        # Scroll distance based on session profile
        distance = random.randint(
            max(200, profile.scroll_speed - 200),
            profile.scroll_speed + 200,
        )

        # Mix: 50/50 JS scrollBy vs mouse.wheel
        if random.random() < 0.5:
            await page.evaluate(f"window.scrollBy(0, {distance})")
        else:
            await page.mouse.wheel(0, distance)

        logger.debug(f"Scroll pass {i + 1}/{passes}: {distance}px")

        # Post-scroll pause
        await asyncio.sleep(random.uniform(1.5, 6.0))

        # 25% chance: scroll back up a bit
        if random.random() < 0.25:
            back_distance = random.randint(100, 400)
            if random.random() < 0.5:
                await page.evaluate(f"window.scrollBy(0, -{back_distance})")
            else:
                await page.mouse.wheel(0, -back_distance)
            logger.debug(f"Scroll back up: {back_distance}px")
            await asyncio.sleep(random.uniform(0.5, 2.0))


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


# ---------------------------------------------------------------------------
# New functions
# ---------------------------------------------------------------------------

async def rethink_comment(page: Page, selector: str, full_text: str) -> str:
    """
    Type a comment with a mid-stream "rethink" — delete some words and retype.

    - Types 60-90% of full_text via type_slowly()
    - Deletes last 1-6 words via repeated Backspace (realistic speed)
    - Pauses 1.5-4.0s (rethink)
    - Retypes the deleted portion + remaining text
    - 12% chance: deletes everything and returns "" (caller should retry)

    Returns the final text that was typed.
    """
    # 12% chance: type a bit, delete everything, bail out
    if random.random() < 0.12:
        partial_len = random.randint(10, max(11, len(full_text) // 3))
        partial = full_text[:partial_len]
        await type_slowly(page, selector, partial)
        await asyncio.sleep(random.uniform(1.0, 2.5))
        # Delete everything via Backspace
        for _ in range(len(partial)):
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.03, 0.08))
        await asyncio.sleep(random.uniform(2.0, 5.0))
        logger.info("rethink_comment: deleted entire comment (12% bail)")
        return ""

    # Type 60-90% of the text
    cut_ratio = random.uniform(0.6, 0.9)
    cut_index = int(len(full_text) * cut_ratio)
    # Snap forward to word boundary
    while cut_index < len(full_text) and full_text[cut_index] != " ":
        cut_index += 1
    typed_portion = full_text[:cut_index]
    remaining_portion = full_text[cut_index:]

    await type_slowly(page, selector, typed_portion)

    # Delete last 1-6 words via Backspace
    words = typed_portion.split()
    words_to_delete = min(random.randint(1, 6), max(1, len(words)))
    deleted_words = words[-words_to_delete:]
    kept_words = words[:-words_to_delete]

    # Calculate chars to backspace (deleted words + separating spaces)
    chars_to_delete = sum(len(w) for w in deleted_words) + words_to_delete
    chars_to_delete = min(chars_to_delete, len(typed_portion))

    await asyncio.sleep(random.uniform(0.5, 1.5))
    for _ in range(chars_to_delete):
        await page.keyboard.press("Backspace")
        await asyncio.sleep(random.uniform(0.04, 0.1))

    # Rethink pause
    await asyncio.sleep(random.uniform(1.5, 4.0))

    # Retype the deleted portion + remaining text
    retype_text = " ".join(deleted_words) + remaining_portion
    if kept_words:
        retype_text = " " + retype_text  # space after kept portion

    for char in retype_text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.04, 0.12))

    final_text = " ".join(kept_words) + retype_text
    logger.debug(
        f"rethink_comment: deleted {words_to_delete} words, retyped {len(retype_text)} chars"
    )
    return final_text


async def move_mouse(page: Page, target_x: int, target_y: int) -> None:
    """
    Move the mouse to (target_x, target_y) along a Bezier curve path.

    - Cubic Bezier with random control-point offsets +/-30-120px
    - Micro-tremor +/-1-3px at each step
    - Overshoot based on SessionProfile.mouse_overshoot, then correct back
    - 10-30% chance: drift to a random viewport spot mid-path (distracted cursor)
    - Hover at target for 200-900ms
    """
    profile = get_session_profile()

    # Get current mouse position (tracked via JS global, default to random spot)
    try:
        current = await page.evaluate(
            "(() => ({ x: window._mouseX || 0, y: window._mouseY || 0 }))()"
        )
        cx, cy = current.get("x", 0), current.get("y", 0)
    except Exception:
        cx, cy = random.randint(100, 600), random.randint(100, 400)

    # 10-30% chance: drift to a random area first (distracted cursor)
    drift_chance = random.uniform(0.10, 0.30)
    if random.random() < drift_chance:
        vw = await page.evaluate("window.innerWidth") or 1366
        vh = await page.evaluate("window.innerHeight") or 768
        drift_x = random.randint(50, max(51, vw - 50))
        drift_y = random.randint(50, max(51, vh - 50))
        drift_path = _generate_bezier_path(cx, cy, drift_x, drift_y, overshoot=0.0)
        for px, py in drift_path:
            await page.mouse.move(px, py)
            await asyncio.sleep(random.uniform(0.002, 0.008))
        logger.debug(f"move_mouse: distracted drift to ({drift_x}, {drift_y})")
        cx, cy = drift_x, drift_y
        await asyncio.sleep(random.uniform(0.3, 1.0))

    # Main path with overshoot
    path = _generate_bezier_path(
        cx, cy, float(target_x), float(target_y),
        overshoot=profile.mouse_overshoot,
    )
    for px, py in path:
        await page.mouse.move(px, py)
        await asyncio.sleep(random.uniform(0.002, 0.01))

    # Track position for next call
    await page.evaluate(
        f"window._mouseX = {target_x}; window._mouseY = {target_y};"
    )

    # Hover at target
    hover_time = random.uniform(0.2, 0.9)
    await asyncio.sleep(hover_time)
    logger.debug(f"move_mouse: arrived at ({target_x}, {target_y}), hovered {hover_time:.2f}s")


async def scroll_to_post(page: Page, post_element) -> None:
    """
    Scroll until a post element is roughly centered in the viewport.
    Uses smooth, Bezier-style eased increments (smoothstep).
    """
    box = await post_element.bounding_box()
    if not box:
        logger.warning("scroll_to_post: element has no bounding box")
        return

    viewport = await page.evaluate(
        "({ vh: window.innerHeight, scrollY: window.scrollY })"
    )
    vh = viewport.get("vh", 768)
    scroll_y = viewport.get("scrollY", 0)

    # Target: element center aligned to viewport center
    element_center_y = box["y"] + box["height"] / 2
    target_scroll = element_center_y - vh / 2
    total_delta = target_scroll - scroll_y

    if abs(total_delta) < 50:
        return  # Already close enough

    # Ease with smoothstep in 8-15 incremental steps
    steps = random.randint(8, 15)
    for i in range(1, steps + 1):
        t = i / steps
        # Smoothstep easing: 3t^2 - 2t^3
        t_eased = t * t * (3.0 - 2.0 * t)
        target_pos = scroll_y + total_delta * t_eased
        current_pos = await page.evaluate("window.scrollY")
        delta = int(target_pos - current_pos)

        if abs(delta) > 0:
            await page.mouse.wheel(0, delta)

        await asyncio.sleep(random.uniform(0.03, 0.08))

    # Final settle pause
    await asyncio.sleep(random.uniform(0.3, 1.0))
    logger.debug(f"scroll_to_post: scrolled {total_delta:.0f}px to center element")


async def session_start_delay() -> None:
    """
    Delay before the first browser action in a session.

    - Logs the session profile details
    - 8% chance: raises SkipSessionException (caller should abort session)
    - Base delay: random 8-45s
    """
    profile = get_session_profile()

    logger.info(
        f"Session profile: wpm={profile.wpm}, "
        f"pause_profile={profile.pause_profile}, "
        f"typo_rate={profile.typo_rate:.3f}, "
        f"mouse_overshoot={profile.mouse_overshoot:.3f}, "
        f"scroll_speed={profile.scroll_speed}"
    )

    # 8% chance: skip this session entirely
    if random.random() < 0.08:
        logger.info("session_start_delay: SKIP_SESSION triggered (8% chance)")
        raise SkipSessionException("Random session skip triggered")

    delay = random.uniform(8.0, 45.0)
    logger.info(f"Session start delay: {delay:.1f}s")
    await asyncio.sleep(delay)
