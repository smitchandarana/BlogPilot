"""
Pipeline — Sprint 4 + Sprint 5 AI wiring.

Full post-processing pipeline. Called by the worker pool as a sync function.
Each call creates its own asyncio event loop + browser session for thread safety.

Pipeline steps (10):
  1.  Scheduler fires → worker pool receives task
  2.  Feed scan (navigate, scroll, DOM extract)
  3.  Deduplicate against DB
  4.  AI relevance score  (Groq via relevance_classifier)
  5.  Viral check         (stub → Sprint 7 replaces)
  6.  Strategy decision   (stub → Sprint 7 replaces)
  7.  Comment generation  (Groq via comment_generator)
  8.  Human delay
  9.  Execute action (like / comment / connect)
  10. Log + WebSocket push
"""
import asyncio
import json
import os
from typing import Optional, Tuple

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ── AI dependency factory ──────────────────────────────────────────────────

def _load_groq_key() -> str:
    """
    Resolve GROQ API key.
    Priority: GROQ_API_KEY env var → config/.secrets/groq.json → empty string.
    """
    key = os.environ.get("GROQ_API_KEY", "")
    if key:
        return key

    secrets_file = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets", "groq.json")
    )
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r") as f:
                data = json.load(f)
            return data.get("api_key", "")
        except Exception as e:
            logger.warning(f"Pipeline: failed to read groq.json: {e}")

    return ""


def _build_ai_deps():
    """
    Instantiate GroqClient + PromptLoader.
    Returns (groq_client, prompt_loader) or (None, None) if no API key.
    """
    from backend.ai.groq_client import GroqClient, GroqError
    from backend.ai.prompt_loader import PromptLoader

    api_key = _load_groq_key()
    if not api_key:
        logger.warning("Pipeline: GROQ_API_KEY not configured — AI steps will use fallback")
        return None, None

    try:
        client = GroqClient(
            api_key=api_key,
            model=str(cfg_get("ai.model", "llama3-70b-8192")),
            max_tokens=int(cfg_get("ai.max_tokens", 500)),
            temperature=float(cfg_get("ai.temperature", 0.7)),
        )
        loader = PromptLoader()
        loader.load_all()
        return client, loader
    except GroqError as e:
        logger.error(f"Pipeline: failed to build GroqClient: {e}")
        return None, None


# ── Public sync entry points (called by worker pool) ──────────────────────

def run_feed_scan():
    """
    Sync entry point called by the worker pool.
    Spawns a fresh asyncio event loop and runs the full async pipeline.
    """
    logger.info("Pipeline: run_feed_scan triggered")
    try:
        asyncio.run(_async_feed_scan())
    except Exception as e:
        logger.error(f"Pipeline: run_feed_scan failed: {e}", exc_info=True)


def process_post(post_data: dict):
    """
    Sync entry point to process a single post (submitted directly to queue).
    """
    url = post_data.get("url", "unknown")
    logger.info(f"Pipeline: process_post triggered — {url}")
    try:
        asyncio.run(_async_process_single(post_data))
    except Exception as e:
        logger.error(f"Pipeline: process_post failed: {e}", exc_info=True)


# ── Async pipeline implementation ─────────────────────────────────────────

async def _async_feed_scan():
    """Full async feed scan: login → scan → process each post."""
    from backend.automation.browser import BrowserManager
    from backend.automation.linkedin_login import LinkedInLogin
    from backend.automation.feed_scanner import FeedScanner
    from backend.automation.interaction_engine import InteractionEngine
    from backend.storage.database import get_db
    from backend.core.engine import get_engine

    engine = get_engine()

    # Guard: only run if engine is RUNNING
    if engine:
        from backend.core.state_manager import EngineState
        if engine.state_manager.get() != EngineState.RUNNING:
            logger.info("Pipeline: engine not RUNNING — aborting")
            return

    # Guard: activity window check
    if not _in_activity_window():
        logger.info("Pipeline: outside activity window — skipping")
        return

    cb = engine.circuit_breaker if engine else None

    # Build AI deps once per scan (shared across all posts)
    groq_client, prompt_loader = _build_ai_deps()

    browser = BrowserManager()
    try:
        await browser.launch()
        page = await browser.get_page()

        # Ensure logged in
        login = LinkedInLogin()
        if not await login.is_logged_in(page):
            logger.info("Pipeline: not logged in — attempting login")
            ok = await login.login(page)
            if not ok:
                logger.error("Pipeline: login failed — aborting scan")
                return

        # Step 2: Scan feed
        scanner = FeedScanner()
        ie = InteractionEngine(circuit_breaker=cb)

        with get_db() as db:
            # Step 3: Deduplication happens inside scan()
            posts = await scanner.scan(page, db=db)
            if not posts:
                logger.info("Pipeline: no new posts found")
                return

            logger.info(f"Pipeline: processing {len(posts)} new posts")

            for post in posts:
                # Re-check engine state between posts
                if engine:
                    from backend.core.state_manager import EngineState
                    if engine.state_manager.get() != EngineState.RUNNING:
                        logger.info("Pipeline: engine stopped mid-scan — halting")
                        break
                await _process_post(post, page, ie, db, engine, groq_client, prompt_loader)

    finally:
        await browser.close()

    logger.info("Pipeline: feed scan complete")


async def _async_process_single(post_data: dict):
    """Process a single post (used when submitted directly to queue)."""
    from backend.automation.browser import BrowserManager
    from backend.automation.interaction_engine import InteractionEngine
    from backend.storage.database import get_db
    from backend.core.engine import get_engine

    engine = get_engine()
    cb = engine.circuit_breaker if engine else None

    groq_client, prompt_loader = _build_ai_deps()

    browser = BrowserManager()
    try:
        await browser.launch()
        page = await browser.get_page()
        ie = InteractionEngine(circuit_breaker=cb)
        with get_db() as db:
            await _process_post(post_data, page, ie, db, engine, groq_client, prompt_loader)
    finally:
        await browser.close()


async def _process_post(post: dict, page, ie, db, engine, groq_client=None, prompt_loader=None) -> None:
    """
    Run the full pipeline (steps 3-10) on a single extracted post.
    """
    from backend.automation.human_behavior import random_delay
    from backend.storage import post_state

    url = post.get("url", "")
    author = post.get("author_name", "Unknown")

    if not url:
        return

    # Step 3: Mark post as seen immediately to prevent double-processing
    post_state.mark_seen(
        url, db,
        author_name=author,
        author_url=post.get("author_url", ""),
        text=post.get("text", ""),
        like_count=int(post.get("like_count", 0)),
        comment_count=int(post.get("comment_count", 0)),
    )

    # Step 4: Score for relevance (Groq AI)
    score = await _score_post(post, groq_client, prompt_loader)
    min_score = float(cfg_get("feed_engagement.min_relevance_score", 6))

    if score < min_score:
        post_state.update_state(
            url, "SKIPPED", db,
            relevance_score=score,
            skip_reason=f"score {score:.1f} < threshold {min_score}",
        )
        logger.info(f"Pipeline: SKIP '{author}' score={score:.1f}")
        return

    post_state.update_state(url, "SCORED", db, relevance_score=score)
    logger.info(f"Pipeline: scored '{author}' score={score:.1f}")

    # Step 5: Viral check — adjust queue priority (informational at this stage)
    try:
        from backend.growth import viral_detector
        post_ts = post.get("timestamp")  # datetime or None
        viral = viral_detector.is_viral(
            like_count=int(post.get("like_count", 0)),
            comment_count=int(post.get("comment_count", 0)),
            post_timestamp=post_ts,
        )
        if viral:
            logger.info(f"Pipeline: VIRAL post detected — '{author}'")
    except Exception as e:
        logger.debug(f"Pipeline: viral_detector unavailable — {e}")

    # Step 6: Strategy decision (Sprint 7 engagement_strategy)
    mode = str(cfg_get("feed_engagement.mode", "smart"))
    try:
        from backend.growth import engagement_strategy
        budget_flags = engagement_strategy.get_budget_flags(db)
        action = engagement_strategy.decide(score, budget_flags, mode)
    except Exception:
        action = _decide_action(score, mode, db)

    if action == "SKIP":
        post_state.update_state(url, "SKIPPED", db, skip_reason="budget/strategy skip")
        return

    # Step 7: Generate comment (Groq AI — Sprint 5; stub now)
    comment_text: Optional[str] = None
    if action in ("COMMENT", "LIKE_AND_COMMENT"):
        comment_text = await _generate_comment(post, groq_client, prompt_loader)

        # Preview mode: push to UI and wait for human approval before posting
        if bool(cfg_get("feed_engagement.preview_comments", True)):
            try:
                from backend.api.websocket import schedule_broadcast
                schedule_broadcast("post_preview", {
                    "url": url,
                    "author": author,
                    "text": post.get("text", "")[:200],
                    "comment": comment_text,
                    "score": score,
                })
            except Exception:
                pass
            post_state.update_state(url, "PREVIEW", db, relevance_score=score, comment_text=comment_text)
            logger.info(f"Pipeline: PREVIEW sent for '{author}' — awaiting approval")
            return

    # Step 8: Human delay between posts
    await random_delay(
        float(cfg_get("delays.between_posts_min", 4)),
        float(cfg_get("delays.between_posts_max", 15)),
    )

    # Step 9: Execute action(s)
    acted = False

    if action in ("LIKE", "LIKE_AND_COMMENT"):
        ok = await ie.like_post(page, url, db=db)
        if ok:
            acted = True

    if action in ("COMMENT", "LIKE_AND_COMMENT") and comment_text:
        ok = await ie.comment_post(page, url, comment_text, db=db)
        if ok:
            acted = True

    # Step 10: Update post state + WebSocket
    final_state = "ACTED" if acted else "FAILED"
    post_state.update_state(
        url, final_state, db,
        relevance_score=score,
        action_taken=action,
        comment_text=comment_text,
    )
    logger.info(f"Pipeline: {final_state} '{author}' action={action} score={score:.1f}")

    # High-score profile visit (leads to email enrichment in Sprint 6)
    visit_threshold = float(cfg_get("feed_engagement.score_for_profile_visit", 8))
    if score >= visit_threshold and post.get("author_url"):
        await _visit_profile(post["author_url"], page, db, score, engine)


async def _visit_profile(
    profile_url: str, page, db, score: float, engine
) -> None:
    """Visit and scrape a high-value profile; run email enrichment; optionally connect."""
    from backend.automation.profile_scraper import ProfileScraper
    from backend.automation.interaction_engine import InteractionEngine

    logger.info(f"Pipeline: visiting profile {profile_url}")
    scraper = ProfileScraper()
    profile_data = await scraper.scrape(page, profile_url, db=db)

    # Email enrichment — page is already on the profile
    if cfg_get("email_enrichment.enabled", True):
        try:
            from backend.enrichment.email_enricher import EmailEnricher

            enricher = EmailEnricher(page=page)
            enrich_result = await enricher.enrich(profile_data)
            email = enrich_result.get("email")
            method = enrich_result.get("method")
            if email:
                logger.info(f"Pipeline: email found via {method}: {email}")
            else:
                logger.info(f"Pipeline: no email found for {profile_url}")
        except Exception as e:
            logger.warning(f"Pipeline: email enrichment failed — {e}")

    # Connection request at maximum score threshold
    connect_threshold = float(cfg_get("feed_engagement.score_for_connection", 10))
    if score >= connect_threshold:
        cb = engine.circuit_breaker if engine else None
        ie = InteractionEngine(circuit_breaker=cb)
        await ie.connect_with(page, profile_url, db=db)


# ── AI scoring (Groq) ─────────────────────────────────────────────────────

async def _score_post(post: dict, groq_client=None, prompt_loader=None) -> float:
    """
    Score post relevance via Groq AI.
    Falls back to keyword-overlap if no API key is configured.
    """
    topics_cfg = cfg_get("topics", [])

    # Groq path
    if groq_client and prompt_loader:
        try:
            from backend.ai import relevance_classifier
            if isinstance(topics_cfg, list):
                topics_str = ", ".join(str(t) for t in topics_cfg)
            else:
                topics_str = str(topics_cfg)
            result = await relevance_classifier.classify(
                post_text=post.get("text", ""),
                author_name=post.get("author_name", "Unknown"),
                topics=topics_str,
                groq_client=groq_client,
                prompt_loader=prompt_loader,
            )
            return float(result.get("score", 0))
        except Exception as e:
            logger.warning(f"Pipeline: Groq scoring failed, falling back to keyword: {e}")

    # Fallback: keyword-overlap
    text = (post.get("text") or "").lower()
    if isinstance(topics_cfg, list):
        topic_words = set(" ".join(str(t) for t in topics_cfg).lower().split())
    else:
        topic_words = set(str(topics_cfg).lower().split())

    if not topic_words:
        return 5.0

    post_words = set(text.split())
    overlap = len(topic_words & post_words)

    if overlap >= 5:
        return 8.0
    elif overlap >= 3:
        return 7.0
    elif overlap >= 1:
        return 6.0
    return 3.0


# ── AI comment generation (Groq) ──────────────────────────────────────────

async def _generate_comment(post: dict, groq_client=None, prompt_loader=None) -> str:
    """
    Generate a LinkedIn comment via Groq AI.
    Falls back to a generic stub if no API key is configured.
    """
    if groq_client and prompt_loader:
        try:
            from backend.ai import comment_generator
            topics_cfg = cfg_get("topics", [])
            tone = str(cfg_get("content_studio.default_tone", "professional"))
            result = await comment_generator.generate(
                post_text=post.get("text", ""),
                author_name=post.get("author_name", "Unknown"),
                topics=topics_cfg,
                tone=tone,
                groq_client=groq_client,
                prompt_loader=prompt_loader,
            )
            if result:
                return result
        except Exception as e:
            logger.warning(f"Pipeline: Groq comment generation failed, using fallback: {e}")

    # Fallback stub
    author = post.get("author_name", "the author")
    return f"Thanks for sharing this perspective, {author}. Really valuable insight."


# ── Action decision (replaced by engagement_strategy in Sprint 7) ──────────

def _decide_action(score: float, mode: str, db) -> str:
    """
    Decide action based on score + mode + remaining budget.
    Returns: 'LIKE' | 'COMMENT' | 'LIKE_AND_COMMENT' | 'SKIP'
    Sprint 7 replaces this with backend.growth.engagement_strategy.
    """
    from backend.storage import budget_tracker

    can_like = budget_tracker.check("likes", db)
    can_comment = budget_tracker.check("comments", db)

    if mode == "like_only":
        return "LIKE" if can_like else "SKIP"

    if mode == "comment_only":
        return "COMMENT" if can_comment else "SKIP"

    if mode == "like_and_comment":
        if can_like and can_comment:
            return "LIKE_AND_COMMENT"
        if can_like:
            return "LIKE"
        return "SKIP"

    # smart (default)
    if score >= 8 and can_like and can_comment:
        return "LIKE_AND_COMMENT"
    if score >= 6 and can_like:
        return "LIKE"
    return "SKIP"


# ── Activity window guard ──────────────────────────────────────────────────

def _in_activity_window() -> bool:
    """
    Return True if the current local time is within the configured
    start_hour / end_hour window on an active day.
    """
    try:
        import datetime

        start = int(cfg_get("schedule.start_hour", 9))
        end = int(cfg_get("schedule.end_hour", 18))
        active_days = cfg_get(
            "schedule.active_days",
            ["monday", "tuesday", "wednesday", "thursday", "friday"],
        )
        tz_name = cfg_get("schedule.timezone", "UTC")

        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(tz_name)
            now = datetime.datetime.now(tz)
        except Exception:
            now = datetime.datetime.now()

        day_name = now.strftime("%A").lower()
        return day_name in [d.lower() for d in active_days] and start <= now.hour < end
    except Exception:
        return True  # Fail open — don't block engine on config error
