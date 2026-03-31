"""
Interaction engine — Sprint 4.

Executes LinkedIn actions: like, comment, connect, follow, endorse, message.

Every action:
  1. Checks daily budget before executing
  2. Applies a human-like random delay
  3. Attempts the action, retries ONCE on failure
  4. Records success/failure to engagement_log
  5. Increments budget counter on success
  6. Reports to circuit_breaker
  7. Broadcasts WebSocket activity event
"""
import asyncio
from typing import Optional

from playwright.async_api import Page

from backend.automation.human_behavior import random_delay
from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Action type keys — must match budget_tracker / engagement_log entries
ACTION_LIKE = "likes"
ACTION_COMMENT = "comments"
ACTION_CONNECT = "connections"
ACTION_FOLLOW = "follows"
ACTION_ENDORSE = "endorsements"
ACTION_MESSAGE = "messages"
ACTION_INMAIL = "inmails"
ACTION_VISIT = "profile_visits"


class InteractionEngine:
    """LinkedIn interaction executor with budget enforcement and safety wrappers."""

    def __init__(self, circuit_breaker=None, budget_tracker=None, engagement_log=None, broadcast_fn=None):
        self._cb = circuit_breaker
        self._budget_tracker = budget_tracker
        self._engagement_log = engagement_log
        self._broadcast_fn = broadcast_fn or (lambda event, payload: None)

    # ── Like ────────────────────────────────────────────────────────────────

    async def like_post(self, page: Page, post_url: str, db=None, author_name: str = "", topic_tag: str = "") -> bool:
        if not self._budget_ok(ACTION_LIKE, db):
            return False
        await random_delay(
            float(cfg_get("delays.before_like_min", 3)),
            float(cfg_get("delays.before_like_max", 12)),
        )
        ok = await self._attempt_like(page, post_url, author_name)
        if not ok:
            await asyncio.sleep(2)
            ok = await self._attempt_like(page, post_url, author_name)
        self._record(ok, ACTION_LIKE, post_url, db, target_name=author_name, topic_tag=topic_tag)
        return ok

    async def _attempt_like(self, page: Page, post_url: str, author_name: str = "") -> bool:
        try:
            # If URL is a real HTTP link, navigate to the post page
            if post_url.startswith("http"):
                await page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(1.5)
                return await self._click_like_on_page(page)

            # Synthetic URL (urn:li:feedpost:...) — interact on the current feed page
            logger.info(f"Like: non-navigable URL, trying in-feed like for '{author_name}'")
            return await self._like_in_feed(page, author_name)

        except Exception as e:
            logger.warning(f"Like attempt error: {e}")
            return False

    async def _click_like_on_page(self, page: Page) -> bool:
        """Find and click the like button on the current page (post detail or feed)."""
        # New LinkedIn DOM: reaction button with aria-label
        btn = await page.query_selector(
            "button[aria-label='Reaction button state: no reaction'], "
            "button[aria-label*='Like'][aria-pressed='false'], "
            "button.reactions-react-button[aria-pressed='false']"
        )
        if not btn:
            logger.debug("Like button not found or post already liked")
            return False

        await btn.hover()
        await asyncio.sleep(0.4)
        await btn.click()
        await asyncio.sleep(1.2)

        # Verify — check if the button state changed
        liked = await page.query_selector(
            "button[aria-label*='reaction'][aria-pressed='true'], "
            "button[aria-label*='Like'][aria-pressed='true'], "
            "button.reactions-react-button[aria-pressed='true']"
        )
        return liked is not None

    async def _like_in_feed(self, page: Page, author_name: str) -> bool:
        """Like a post directly on the feed page by finding the post via author name."""
        if not author_name:
            logger.warning("Like in-feed: no author name — cannot locate post")
            return False

        # Find the post container via the author's control menu button
        result = await page.evaluate("""(authorName) => {
            // Find the "control menu for post by <author>" button
            const buttons = document.querySelectorAll('button[aria-label*="control menu for post by"]');
            for (const btn of buttons) {
                const label = btn.getAttribute('aria-label') || '';
                if (label.includes(authorName)) {
                    // Walk up to the post container (data-display-contents wrapper)
                    let container = btn.closest('[data-display-contents="true"]');
                    if (!container) {
                        // Fallback: walk up to find a reasonable ancestor
                        container = btn.parentElement;
                        for (let i = 0; i < 8 && container; i++) {
                            if (container.querySelector('button[aria-label*="Reaction button"]')) break;
                            container = container.parentElement;
                        }
                    }
                    if (!container) return null;

                    // Find the reaction button (not yet reacted)
                    const reactBtn = container.querySelector(
                        'button[aria-label="Reaction button state: no reaction"]'
                    );
                    if (reactBtn) {
                        // Return a selector path to click it
                        // Use the button's position in the DOM
                        reactBtn.setAttribute('data-bp-click-target', 'true');
                        return true;
                    }
                    return null;  // Already liked or no button found
                }
            }
            return null;
        }""", author_name)

        if not result:
            logger.debug(f"Like in-feed: could not locate reaction button for '{author_name}'")
            return False

        # Click the marked button
        btn = await page.query_selector('button[data-bp-click-target="true"]')
        if not btn:
            return False

        # Clean up the marker attribute
        await page.evaluate("""() => {
            const el = document.querySelector('[data-bp-click-target]');
            if (el) el.removeAttribute('data-bp-click-target');
        }""")

        await btn.hover()
        await asyncio.sleep(0.4)
        await btn.click()
        await asyncio.sleep(1.2)
        logger.info(f"Liked in-feed post by '{author_name}'")
        return True

    # ── Comment ────────────────────────────────────────────────────────────

    async def comment_post(
        self, page: Page, post_url: str, comment_text: str, db=None, author_name: str = "", topic_tag: str = ""
    ) -> bool:
        if not self._budget_ok(ACTION_COMMENT, db):
            return False
        await random_delay(
            float(cfg_get("delays.before_comment_min", 8)),
            float(cfg_get("delays.before_comment_max", 45)),
        )
        ok = await self._attempt_comment(page, post_url, comment_text, author_name)
        if not ok:
            await asyncio.sleep(3)
            ok = await self._attempt_comment(page, post_url, comment_text, author_name)
        self._record(ok, ACTION_COMMENT, post_url, db, comment_text=comment_text, target_name=author_name, topic_tag=topic_tag)
        return ok

    async def _attempt_comment(
        self, page: Page, post_url: str, comment_text: str, author_name: str = ""
    ) -> bool:
        try:
            # Navigate to post if it has a real URL
            if post_url.startswith("http"):
                await page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2.0)
            else:
                # Non-navigable URL — scroll to post on feed page
                logger.info(f"Comment: non-navigable URL, trying in-feed comment for '{author_name}'")
                if author_name:
                    scrolled = await self._scroll_to_post_in_feed(page, author_name)
                    if not scrolled:
                        logger.warning(f"Could not locate post by '{author_name}' in feed")
                        return False

            # Open comment area
            comment_btn = await page.query_selector(
                "button[aria-label*='Comment'], "
                "span:text-is('Comment')"
            )
            if comment_btn:
                await comment_btn.click()
                await asyncio.sleep(1.0)

            # Find contenteditable comment box
            editor = await page.query_selector(
                "div.ql-editor[contenteditable='true'], "
                "div[role='textbox'][aria-label*='comment' i], "
                "div[role='textbox'][contenteditable='true'], "
                "div.comments-comment-box__form div[contenteditable='true']"
            )
            if not editor:
                logger.warning("Comment editor not found")
                return False

            await editor.click()
            await asyncio.sleep(0.4)

            # Type character by character
            for char in comment_text:
                await page.keyboard.type(char)
                await asyncio.sleep(0.05)

            await asyncio.sleep(1.0)

            # Submit
            submit = await page.query_selector(
                "button.comments-comment-box__submit-button--cr, "
                "button[aria-label='Post comment' i], "
                "button:text-is('Post')"
            )
            if not submit:
                logger.warning("Comment submit button not found")
                return False

            await submit.click()
            await asyncio.sleep(2.5)
            logger.info(f"Comment posted on {post_url[:80]}")
            return True
        except Exception as e:
            logger.warning(f"Comment attempt error: {e}")
            return False

    async def _scroll_to_post_in_feed(self, page: Page, author_name: str) -> bool:
        """Scroll the feed to bring a specific post into view, by author name."""
        try:
            found = await page.evaluate("""(authorName) => {
                const buttons = document.querySelectorAll('button[aria-label*="control menu for post by"]');
                for (const btn of buttons) {
                    if ((btn.getAttribute('aria-label') || '').includes(authorName)) {
                        btn.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        return true;
                    }
                }
                return false;
            }""", author_name)
            if found:
                await asyncio.sleep(1.0)
            return found
        except Exception:
            return False

    # ── Connect ────────────────────────────────────────────────────────────

    async def connect_with(
        self,
        page: Page,
        profile_url: str,
        note: Optional[str] = None,
        db=None,
    ) -> bool:
        if not self._budget_ok(ACTION_CONNECT, db):
            return False
        await random_delay(
            float(cfg_get("delays.before_connect_min", 5)),
            float(cfg_get("delays.before_connect_max", 20)),
        )
        ok = await self._attempt_connect(page, profile_url, note)
        if not ok:
            await asyncio.sleep(3)
            ok = await self._attempt_connect(page, profile_url, note)
        self._record(ok, ACTION_CONNECT, profile_url, db)
        return ok

    async def _attempt_connect(
        self, page: Page, profile_url: str, note: Optional[str]
    ) -> bool:
        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2.0)

            connect_btn = await page.query_selector(
                "button[aria-label*='Connect' i], "
                "button:text-is('Connect')"
            )
            if not connect_btn:
                logger.debug(f"Connect button not found on {profile_url}")
                return False

            await connect_btn.click()
            await asyncio.sleep(1.5)

            # Optionally add a personalised note
            if note:
                add_note_btn = await page.query_selector(
                    "button[aria-label='Add a note' i], "
                    "button:text-is('Add a note')"
                )
                if add_note_btn:
                    await add_note_btn.click()
                    await asyncio.sleep(0.8)
                    note_box = await page.query_selector(
                        "textarea[name='message'], "
                        "textarea[aria-label*='note' i]"
                    )
                    if note_box:
                        await note_box.fill(note[:300])
                        await asyncio.sleep(0.5)

            # Confirm send
            send_btn = await page.query_selector(
                "button[aria-label='Send now' i], "
                "button[aria-label='Send invitation' i], "
                "button:text-is('Send')"
            )
            if send_btn:
                await send_btn.click()
                await asyncio.sleep(1.5)
                logger.info(f"Connection request sent: {profile_url}")
                return True

            return False
        except Exception as e:
            logger.warning(f"Connect attempt error: {e}")
            return False

    # ── Follow ─────────────────────────────────────────────────────────────

    async def follow(self, page: Page, profile_url: str, db=None) -> bool:
        if not self._budget_ok(ACTION_FOLLOW, db):
            return False
        await random_delay(2.0, 8.0)
        ok = await self._attempt_follow(page, profile_url)
        if not ok:
            await asyncio.sleep(2)
            ok = await self._attempt_follow(page, profile_url)
        self._record(ok, ACTION_FOLLOW, profile_url, db)
        return ok

    async def _attempt_follow(self, page: Page, profile_url: str) -> bool:
        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2.0)
            btn = await page.query_selector(
                "button[aria-label*='Follow' i]:not([aria-label*='Unfollow' i]), "
                "button:text-is('Follow')"
            )
            if not btn:
                return False
            await btn.click()
            await asyncio.sleep(1.0)
            logger.info(f"Followed {profile_url}")
            return True
        except Exception as e:
            logger.warning(f"Follow attempt error: {e}")
            return False

    # ── Endorse ────────────────────────────────────────────────────────────

    async def endorse_skills(self, page: Page, profile_url: str, db=None) -> bool:
        if not self._budget_ok(ACTION_ENDORSE, db):
            return False
        await random_delay(3.0, 8.0)
        ok = await self._attempt_endorse(page, profile_url)
        self._record(ok, ACTION_ENDORSE, profile_url, db)
        return ok

    async def _attempt_endorse(self, page: Page, profile_url: str) -> bool:
        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2.0)

            skills_section = await page.query_selector(
                "section[id*='skills' i], div[id*='skills' i]"
            )
            if skills_section:
                await skills_section.scroll_into_view_if_needed()
                await asyncio.sleep(1.0)

            btns = await page.query_selector_all(
                "button[aria-label*='Endorse' i], "
                "button[data-control-name='endorse']"
            )
            if not btns:
                return False

            endorsed = 0
            for btn in btns[:3]:
                try:
                    await btn.click()
                    await asyncio.sleep(0.8)
                    endorsed += 1
                except Exception:
                    continue

            logger.info(f"Endorsed {endorsed} skills on {profile_url}")
            return endorsed > 0
        except Exception as e:
            logger.warning(f"Endorse attempt error: {e}")
            return False

    # ── Message ────────────────────────────────────────────────────────────

    async def send_message(
        self, page: Page, profile_url: str, message: str, db=None
    ) -> bool:
        if not self._budget_ok(ACTION_MESSAGE, db):
            return False
        await random_delay(5.0, 15.0)
        ok = await self._attempt_message(page, profile_url, message)
        self._record(ok, ACTION_MESSAGE, profile_url, db, comment_text=message)
        return ok

    async def _attempt_message(
        self, page: Page, profile_url: str, message: str
    ) -> bool:
        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2.0)

            msg_btn = await page.query_selector(
                "button[aria-label*='Message' i], "
                "button:text-is('Message')"
            )
            if not msg_btn:
                logger.debug(f"Message button not found on {profile_url}")
                return False

            await msg_btn.click()
            await asyncio.sleep(1.5)

            msg_input = await page.query_selector(
                "div.msg-form__contenteditable[contenteditable='true'], "
                "div[role='textbox'][aria-label*='Write' i], "
                "div.msg-form__msg-content-container div[contenteditable='true']"
            )
            if not msg_input:
                return False

            await msg_input.click()
            for char in message:
                await page.keyboard.type(char)
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.8)

            send_btn = await page.query_selector(
                "button.msg-form__send-button, "
                "button[aria-label='Send message' i], "
                "button:text-is('Send')"
            )
            if send_btn:
                await send_btn.click()
                await asyncio.sleep(1.0)
                logger.info(f"Message sent to {profile_url}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Message attempt error: {e}")
            return False

    # ── InMail ──────────────────────────────────────────────────────────────

    async def send_inmail(
        self, page: Page, profile_url: str, subject: str, message: str, db=None
    ) -> bool:
        if not self._budget_ok(ACTION_INMAIL, db):
            return False
        await random_delay(5.0, 15.0)
        ok = await self._attempt_inmail(page, profile_url, subject, message)
        self._record(ok, ACTION_INMAIL, profile_url, db, comment_text=message)
        return ok

    async def _attempt_inmail(
        self, page: Page, profile_url: str, subject: str, message: str
    ) -> bool:
        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2.0)

            # Look for InMail / Message button (premium feature)
            msg_btn = await page.query_selector(
                "button[aria-label*='InMail' i], "
                "button[aria-label*='Message' i], "
                "button:text-is('Message')"
            )
            if not msg_btn:
                logger.debug(f"InMail button not found on {profile_url}")
                return False

            await msg_btn.click()
            await asyncio.sleep(1.5)

            # Fill subject line if present
            subject_input = await page.query_selector(
                "input[name='subject'], "
                "input[placeholder*='Subject' i]"
            )
            if subject_input and subject:
                await subject_input.fill(subject)
                await asyncio.sleep(0.5)

            # Fill message body
            msg_input = await page.query_selector(
                "div.msg-form__contenteditable[contenteditable='true'], "
                "div[role='textbox'][aria-label*='Write' i], "
                "textarea[name='message']"
            )
            if not msg_input:
                return False

            await msg_input.click()
            for char in message:
                await page.keyboard.type(char)
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.8)

            send_btn = await page.query_selector(
                "button.msg-form__send-button, "
                "button[aria-label='Send' i], "
                "button:text-is('Send')"
            )
            if send_btn:
                await send_btn.click()
                await asyncio.sleep(1.0)
                logger.info(f"InMail sent to {profile_url}")
                return True
            return False
        except Exception as e:
            logger.warning(f"InMail attempt error: {e}")
            return False

    # ── Internal helpers ────────────────────────────────────────────────────

    def _budget_ok(self, action_type: str, db) -> bool:
        """Return False (and log) if the daily budget is exhausted."""
        if db is None:
            return True  # No DB → no budget enforcement (tests / manual runs)
        if self._budget_tracker is None:
            logger.warning("InteractionEngine: budget_tracker not injected — budget enforcement skipped")
            return True
        try:
            ok = self._budget_tracker.check(action_type, db)
            if not ok:
                logger.info(f"Budget exhausted for '{action_type}' — skipping")
            return ok
        except Exception as e:
            logger.warning(f"Budget check error: {e} — denying action")
            return False  # Fail closed — DB error = deny action

    def _record(
        self,
        success: bool,
        action_type: str,
        target_url: str,
        db,
        comment_text: Optional[str] = None,
        target_name: str = "",
        topic_tag: str = "",
    ) -> None:
        """Log result, increment budget, update circuit breaker, broadcast WS event."""
        result = "SUCCESS" if success else "FAILED"

        # Circuit breaker
        if self._cb:
            if success:
                self._cb.record_success()
            else:
                self._cb.record_error(f"{action_type}_failed")

        # Derive a readable name from URL if none supplied
        if not target_name:
            url_stripped = target_url.rstrip("/")
            if "/in/" in url_stripped:
                target_name = url_stripped.split("/in/")[-1].split("/")[0]
            else:
                # For post URLs: use the last non-empty segment
                parts = [p for p in url_stripped.split("/") if p]
                target_name = parts[-1] if parts else target_url

        if db:
            # Engagement log
            if self._engagement_log is not None:
                try:
                    self._engagement_log.write_action(
                        action_type=action_type,
                        target_url=target_url,
                        target_name=target_name,
                        result=result,
                        db=db,
                        comment_text=comment_text,
                        topic_tag=topic_tag,
                    )
                except Exception as e:
                    logger.warning(f"Engagement log write error: {e}")

            # Budget increment
            if success and self._budget_tracker is not None:
                try:
                    self._budget_tracker.increment(action_type, db)
                except Exception as e:
                    logger.warning(f"Budget increment error: {e}")

        # WebSocket broadcast
        try:
            self._broadcast_fn("activity", {
                "action": action_type,
                "target": target_name,
                "result": result,
                "comment": comment_text,
            })
        except Exception as e:
            logger.debug(f"WebSocket activity broadcast error: {e}")
