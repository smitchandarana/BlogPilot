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
import re
from typing import Optional

from backend.utils.config_loader import get as cfg_get
from backend.utils.logger import get_logger
from backend.ai.client_factory import build_ai_client, AIClientUnavailableError

logger = get_logger(__name__)


# ── AI dependency factory ──────────────────────────────────────────────────

def _build_ai_deps():
    """
    Build AI clients + PromptLoader for the pipeline.

    Returns:
        (background_client, generation_client, prompt_loader)

    background_client — used for relevance scoring (OpenRouter free or Groq fallback).
    generation_client — used for comment generation (Groq only).
    Either client may be None if the corresponding key is not configured;
    callers fall back to heuristics when a client is None.
    """
    from backend.ai.prompt_loader import PromptLoader

    loader = PromptLoader()
    loader.load_all()

    # Background client for relevance scoring
    background_client = build_ai_client("background")
    if background_client is None:
        logger.warning("Pipeline: no background AI client available — relevance scoring will use keyword fallback")

    # Generation client for comment generation
    generation_client = None
    try:
        generation_client = build_ai_client("generation")
    except AIClientUnavailableError:
        logger.warning("Pipeline: Groq API key not configured — comment generation will use fallback")

    return background_client, generation_client, loader


# ── Public sync entry points (called by worker pool) ──────────────────────

def run_feed_scan(force: bool = False):
    """
    Sync entry point called by the worker pool.
    Spawns a fresh asyncio event loop and runs the full async pipeline.
    force=True bypasses the activity-window guard (used by manual scan-now).
    """
    logger.info(f"Pipeline: run_feed_scan triggered (force={force})")
    try:
        asyncio.run(_async_feed_scan(force=force))
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


def run_approve_comment(post_id: str, comment_text: str):
    """
    Sync entry point — called by worker pool when user approves a preview comment.
    Opens the browser, posts the comment on LinkedIn, updates DB state.
    """
    logger.info(f"Pipeline: run_approve_comment triggered — post_id={post_id}")
    try:
        asyncio.run(_async_approve_comment(post_id, comment_text))
    except Exception as e:
        logger.error(f"Pipeline: run_approve_comment failed: {e}", exc_info=True)


# ── Async pipeline implementation ─────────────────────────────────────────

async def _async_feed_scan(force: bool = False):
    """Full async feed scan: login → scan → process each post."""
    from backend.automation.browser import BrowserManager
    from backend.automation.linkedin_login import LinkedInLogin
    from backend.automation.feed_scanner import FeedScanner
    from backend.automation.interaction_engine import InteractionEngine
    from backend.storage.database import get_db
    from backend.storage import post_state as _post_state_mod
    from backend.storage import budget_tracker as _budget_tracker_mod
    from backend.storage import engagement_log as _engagement_log_mod
    from backend.api.websocket import schedule_broadcast
    from backend.core.engine import get_engine

    engine = get_engine()

    # Guard: only run if engine is RUNNING
    if engine:
        from backend.core.state_manager import EngineState
        if engine.state_manager.get() != EngineState.RUNNING:
            logger.info("Pipeline: engine not RUNNING — aborting")
            return

    # Guard: activity window check (skipped for manual scan-now)
    if not force and not _in_activity_window():
        logger.info("Pipeline: outside activity window — skipping")
        return

    cb = engine.circuit_breaker if engine else None

    def _rt(msg: str, level: str = "info"):
        """Emit a runtime_event WebSocket broadcast."""
        try:
            schedule_broadcast("runtime_event", {"message": msg, "level": level})
        except Exception:
            pass

    # Build AI deps once per scan (shared across all posts)
    _rt("Building AI clients…")
    background_client, generation_client, prompt_loader = _build_ai_deps()

    browser = BrowserManager()
    try:
        _rt("Launching browser…")
        await browser.launch()
        page = await browser.get_page()

        # Ensure logged in
        login = LinkedInLogin()
        if not await login.is_logged_in(page):
            _rt("Not logged in — attempting LinkedIn login…", "warning")
            ok = await login.login(page)
            if not ok:
                _rt("Login failed — aborting scan", "error")
                logger.error("Pipeline: login failed — aborting scan")
                return
            _rt("Login successful", "success")
        else:
            _rt("Already logged in via persistent session", "success")

        # Step 2: Scan feed
        _rt("Scanning LinkedIn feed…")
        scanner = FeedScanner(post_state=_post_state_mod)
        ie = InteractionEngine(
            circuit_breaker=cb,
            budget_tracker=_budget_tracker_mod,
            engagement_log=_engagement_log_mod,
            broadcast_fn=schedule_broadcast,
        )

        with get_db() as db:
            # Step 2a: Scan home feed (deduplication happens inside scan())
            posts = await scanner.scan(page, db=db)

            # Step 2b: Hashtag/search scanning (if enabled)
            if cfg_get("feed_engagement.hashtag_scan_enabled", False) or \
               cfg_get("feed_engagement.search_scan_enabled", False):
                try:
                    from backend.automation.hashtag_scanner import HashtagScanner
                    from backend.storage import post_state as _ps
                    ht_scanner = HashtagScanner()
                    hashtags = cfg_get("hashtags", []) or []
                    topics = cfg_get("topics", []) or []
                    extra = await ht_scanner.scan_multiple(page, hashtags, topics)
                    # Deduplicate extra posts against DB
                    for ep in extra:
                        ep_url = ep.get("url", "")
                        if ep_url and not _ps.is_seen(ep_url, db):
                            posts.append(ep)
                    logger.info(f"Pipeline: +{len(extra)} posts from hashtag/search scan")
                except Exception as e:
                    logger.warning(f"Pipeline: hashtag scan error — {e}")

            if not posts:
                _rt("No new posts found", "warning")
                logger.info("Pipeline: no new posts found")
                return

            _rt(f"Found {len(posts)} new posts — processing…", "success")
            logger.info(f"Pipeline: processing {len(posts)} new posts")

            for post in posts:
                # Re-check engine state between posts
                if engine:
                    from backend.core.state_manager import EngineState
                    if engine.state_manager.get() != EngineState.RUNNING:
                        logger.info("Pipeline: engine stopped mid-scan — halting")
                        break
                await _process_post(post, page, ie, db, engine, background_client, generation_client, prompt_loader)

    finally:
        await browser.close()

    logger.info("Pipeline: feed scan complete")


async def _async_process_single(post_data: dict):
    """Process a single post (used when submitted directly to queue)."""
    from backend.automation.browser import BrowserManager
    from backend.automation.interaction_engine import InteractionEngine
    from backend.storage.database import get_db
    from backend.storage import budget_tracker as _budget_tracker_mod
    from backend.storage import engagement_log as _engagement_log_mod
    from backend.api.websocket import schedule_broadcast
    from backend.core.engine import get_engine

    engine = get_engine()
    cb = engine.circuit_breaker if engine else None

    background_client, generation_client, prompt_loader = _build_ai_deps()

    browser = BrowserManager()
    try:
        await browser.launch()
        page = await browser.get_page()
        ie = InteractionEngine(
            circuit_breaker=cb,
            budget_tracker=_budget_tracker_mod,
            engagement_log=_engagement_log_mod,
            broadcast_fn=schedule_broadcast,
        )
        with get_db() as db:
            await _process_post(post_data, page, ie, db, engine, background_client, generation_client, prompt_loader)
    finally:
        await browser.close()


async def _async_approve_comment(post_id: str, comment_text: str):
    """
    Post a user-approved comment on LinkedIn.

    Flow:
      1. Load post record from DB.
      2. Check comment budget.
      3. Open browser + login.
      4. Call interaction_engine.comment_post().
      5. Update post state (ACTED / FAILED).
      6. Log quality metrics + broadcast WebSocket events.
    """
    from backend.automation.browser import BrowserManager
    from backend.automation.linkedin_login import LinkedInLogin
    from backend.automation.interaction_engine import InteractionEngine
    from backend.storage.database import get_db
    from backend.storage import budget_tracker, post_state
    from backend.storage.models import Post
    from backend.core.engine import get_engine

    engine = get_engine()
    cb = engine.circuit_breaker if engine else None

    # ── Load post record ───────────────────────────────────────────────────
    with get_db() as db:
        post = db.query(Post).filter_by(id=post_id).first()
        if not post:
            logger.error(f"Pipeline: approve_comment — post {post_id} not found")
            return
        if post.state != "PREVIEW":
            logger.warning(
                f"Pipeline: approve_comment — post {post_id} state is '{post.state}', expected 'PREVIEW'. "
                "Ignoring (likely a duplicate approval request)."
            )
            return
        # Atomically claim this post to prevent concurrent approvals
        post.state = "APPROVING"
        db.commit()
        url = post.url
        author = post.author_name or "Unknown"
        matched_topic = post.topic_tag or ""
        post_text_for_log = post.text or ""

    # ── Budget check ───────────────────────────────────────────────────────
    with get_db() as db:
        if not budget_tracker.check("comments", db):
            logger.warning("Pipeline: approve_comment — comment budget exhausted")
            post_state.update_state(url, "SKIPPED", db, skip_reason="budget exhausted at approval")
            try:
                from backend.api.websocket import schedule_broadcast as _sched_bc
                _sched_bc("activity", {
                    "action": "COMMENT",
                    "target": author,
                    "result": "SKIPPED",
                    "comment": "Comment budget exhausted",
                })
            except Exception:
                pass
            return

    # ── Open browser + login ───────────────────────────────────────────────
    browser = BrowserManager()
    try:
        await browser.launch()
        page = await browser.get_page()

        login = LinkedInLogin()
        if not await login.is_logged_in(page):
            ok = await login.login(page)
            if not ok:
                logger.error("Pipeline: approve_comment — LinkedIn login failed")
                # Reset state back to PREVIEW so the user can retry
                with get_db() as db:
                    post_state.update_state(url, "PREVIEW", db)
                return

        from backend.storage import engagement_log as _engagement_log_mod
        from backend.api.websocket import schedule_broadcast as _sched_bc
        ie = InteractionEngine(
            circuit_breaker=cb,
            budget_tracker=budget_tracker,
            engagement_log=_engagement_log_mod,
            broadcast_fn=_sched_bc,
        )

        # ── Post the comment ───────────────────────────────────────────────
        with get_db() as db:
            ok = await ie.comment_post(page, url, comment_text, db=db, topic_tag=matched_topic)

            final_state = "ACTED" if ok else "FAILED"
            post_state.update_state(
                url, final_state, db,
                action_taken="COMMENT",
                comment_text=comment_text,
            )

            if ok:
                # Log quality metrics (angle=approved so learning loop can track manual edits)
                try:
                    from backend.storage import quality_log
                    quality_log.log_comment(
                        db=db, post_id=url, post_text=post_text_for_log,
                        comment_used=comment_text, quality_score=0.0,
                        candidate_count=1, topic=matched_topic,
                        all_candidates=None, angle="approved",
                    )
                except Exception as e:
                    logger.debug(f"Pipeline: approve quality log error — {e}")

                # Broadcast budget state to Dashboard
                try:
                    for row in budget_tracker.get_all(db):
                        _sched_bc("budget_update", {
                            "action_type": row.action_type,
                            "count": row.count_today,
                            "limit": row.limit_per_day,
                        })
                except Exception as e:
                    logger.debug(f"Pipeline: approve budget broadcast error — {e}")

        # Broadcast activity event (always, success or fail)
        try:
            _sched_bc("activity", {
                "action": "COMMENT",
                "target": author,
                "result": "SUCCESS" if ok else "FAILED",
                "comment": comment_text,
            })
        except Exception:
            pass

        logger.info(f"Pipeline: approve_comment — {final_state} for '{author}'")

    except Exception as e:
        # Unexpected error (browser launch failure, etc.) — reset to PREVIEW so user can retry
        logger.error(f"Pipeline: approve_comment — unexpected error: {e}", exc_info=True)
        try:
            with get_db() as db:
                post_state.update_state(url, "PREVIEW", db)
        except Exception:
            pass
        raise
    finally:
        await browser.close()


async def _process_post(post: dict, page, ie, db, engine, background_client=None, generation_client=None, prompt_loader=None) -> None:
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

    # Step 3b: Blacklist check — skip before AI scoring to save API calls
    blacklist = cfg_get("keyword_blacklist", [])
    if blacklist:
        text_lower = (post.get("text") or "").lower()
        for phrase in blacklist:
            # Use word-boundary matching to avoid false positives
            # (e.g. "free" should not match "freelancer")
            pattern = r'\b' + re.escape(phrase.lower()) + r'\b'
            if re.search(pattern, text_lower):
                post_state.update_state(
                    url, "SKIPPED", db,
                    skip_reason=f"blacklist: '{phrase}'",
                )
                logger.info(f"Pipeline: BLACKLIST skip '{author}' matched '{phrase}'")
                return

    # Step 4: Score for relevance (background AI client — OpenRouter free or Groq fallback)
    try:
        from backend.api.websocket import schedule_broadcast as _sbc
        _sbc("runtime_event", {"message": f"Scoring post by {author}…", "level": "info"})
    except Exception:
        pass
    score = await _score_post(post, background_client, prompt_loader)
    min_score = float(cfg_get("feed_engagement.min_relevance_score", 6))

    if score < min_score:
        post_state.update_state(
            url, "SKIPPED", db,
            relevance_score=score,
            skip_reason=f"score {score:.1f} < threshold {min_score}",
        )
        try:
            from backend.api.websocket import schedule_broadcast as _sbc
            _sbc("runtime_event", {"message": f"Skip '{author}' — score {score:.1f} < {min_score}", "level": "warning"})
        except Exception:
            pass
        logger.info(f"Pipeline: SKIP '{author}' score={score:.1f}")
        return

    post_state.update_state(url, "SCORED", db, relevance_score=score)
    try:
        from backend.api.websocket import schedule_broadcast as _sbc
        _sbc("runtime_event", {"message": f"✓ '{author}' — score {score:.1f} → queuing action", "level": "success"})
    except Exception:
        pass
    logger.info(f"Pipeline: scored '{author}' score={score:.1f}")

    # Match post against configured topics for performance tracking
    matched_topic = _match_topic(post)

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
    comment_quality_score: float = 0.0
    comment_angle: str = "unknown"
    comment_candidate_count: int = 0
    if action in ("COMMENT", "LIKE_AND_COMMENT"):
        try:
            from backend.api.websocket import schedule_broadcast as _sbc
            _sbc("runtime_event", {"message": f"Generating comment for '{author}'…", "level": "info"})
        except Exception:
            pass
        comment_result = await _generate_comment(post, generation_client, prompt_loader)
        if isinstance(comment_result, dict):
            comment_text = comment_result.get("comment", "")
            comment_quality_score = float(comment_result.get("quality_score", 0))
            comment_angle = comment_result.get("angle", "unknown")
            comment_candidate_count = int(comment_result.get("candidate_count", 0))
            # Reject low-quality or explicitly rejected comments
            if comment_result.get("rejected") or not comment_text:
                reasons = comment_result.get("reject_reasons", ["empty"])
                logger.info(f"Pipeline: comment REJECTED for '{author}' — {reasons}. Downgrading to LIKE.")
                try:
                    from backend.api.websocket import schedule_broadcast
                    schedule_broadcast("activity", {
                        "action": "COMMENT_REJECTED",
                        "target": author,
                        "result": "SKIPPED",
                        "comment": f"Quality too low: {', '.join(reasons[:2])}",
                    })
                except Exception:
                    pass
                comment_text = None
                if action == "COMMENT":
                    action = "LIKE"
                elif action == "LIKE_AND_COMMENT":
                    action = "LIKE"
        else:
            # _generate_comment returned a plain string (fallback path — no Groq key or API error).
            # Never post fallback stub comments; downgrade to LIKE instead.
            comment_text = None
            if action == "COMMENT":
                action = "LIKE"
            elif action == "LIKE_AND_COMMENT":
                action = "LIKE"

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
            try:
                from backend.api.websocket import schedule_broadcast as _sbc
                _sbc("runtime_event", {"message": f"💬 Comment queued for approval — '{author}'", "level": "success"})
            except Exception:
                pass
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
        ok = await ie.like_post(page, url, db=db, author_name=author, topic_tag=matched_topic)
        if ok:
            acted = True

    if action in ("COMMENT", "LIKE_AND_COMMENT") and comment_text:
        ok = await ie.comment_post(page, url, comment_text, db=db, author_name=author, topic_tag=matched_topic)
        if not ok:
            # Retry once after a short delay before giving up
            logger.info(f"Pipeline: comment failed for '{author}' — retrying in 3s")
            await asyncio.sleep(3)
            ok = await ie.comment_post(page, url, comment_text, db=db, author_name=author, topic_tag=matched_topic)
            if not ok:
                logger.warning(f"Pipeline: comment retry also failed for '{author}' — downgrading to LIKE")
        if ok:
            acted = True
            # Log comment quality metrics for self-learning
            try:
                from backend.storage import quality_log
                quality_log.log_comment(
                    db=db, post_id=url, post_text=post.get("text", ""),
                    comment_used=comment_text, quality_score=comment_quality_score,
                    candidate_count=comment_candidate_count, topic=matched_topic,
                    all_candidates=None, angle=comment_angle,
                )
            except Exception as e:
                logger.debug(f"Pipeline: comment quality log error — {e}")

    # Step 10: Update post state + WebSocket
    final_state = "ACTED" if acted else "FAILED"
    post_state.update_state(
        url, final_state, db,
        relevance_score=score,
        action_taken=action,
        comment_text=comment_text,
    )
    logger.info(f"Pipeline: {final_state} '{author}' action={action} score={score:.1f}")

    # Broadcast budget update to Dashboard
    if acted:
        try:
            from backend.api.websocket import schedule_broadcast
            from backend.storage import budget_tracker
            for row in budget_tracker.get_all(db):
                schedule_broadcast("budget_update", {
                    "action_type": row.action_type,
                    "count": row.count_today,
                    "limit": row.limit_per_day,
                })
        except Exception as e:
            logger.debug(f"Pipeline: budget broadcast error — {e}")

    # Track topic engagement for performance-based rotation
    if acted and matched_topic:
        try:
            from backend.growth.topic_rotator import topic_rotator
            topic_rotator.record_engagement(matched_topic, score, action, db)
        except Exception as e:
            logger.debug(f"Pipeline: topic engagement tracking error — {e}")

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
    from backend.storage import budget_tracker as _bt
    from backend.storage import leads_store as _leads_store_mod
    from backend.storage import engagement_log as _engagement_log_mod
    from backend.api.websocket import schedule_broadcast

    if not _bt.check("profile_visits", db):
        logger.info(f"Pipeline: profile_visits budget exhausted — skipping {profile_url}")
        return

    logger.info(f"Pipeline: visiting profile {profile_url}")
    scraper = ProfileScraper(leads_store=_leads_store_mod, broadcast_fn=schedule_broadcast)
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
        ie = InteractionEngine(
            circuit_breaker=cb,
            budget_tracker=_bt,
            engagement_log=_engagement_log_mod,
            broadcast_fn=schedule_broadcast,
        )
        await ie.connect_with(page, profile_url, db=db)

    try:
        _bt.increment("profile_visits", db)
    except Exception as e:
        logger.debug(f"Pipeline: profile_visits budget increment failed — {e}")


# ── AI scoring (Groq) ─────────────────────────────────────────────────────

async def _score_post(post: dict, groq_client=None, prompt_loader=None) -> float:
    """
    Score post relevance via Groq AI.
    Falls back to keyword-overlap if no API key is configured.
    """
    topics_cfg = cfg_get("topics", [])

    # AI scoring path
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
            # If AI returned parse_error, fall through to keyword fallback
            if result.get("reason") == "parse_error":
                logger.warning("Pipeline: AI scoring returned parse_error, falling back to keyword")
            else:
                return float(result.get("score", 0))
        except Exception as e:
            logger.warning(f"Pipeline: AI scoring failed, falling back to keyword: {e}")

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
    except Exception as e:
        # Fail closed — a broken config should not let the engine run 24/7
        logger.warning(f"Activity window check failed, denying: {e}")
        return False


def _match_topic(post: dict) -> str:
    """
    Match post text against configured topics. Returns best matching topic or "".
    Simple word-overlap — picks the topic with the most word matches.
    """
    text = (post.get("text") or "").lower()
    if not text:
        return ""

    topics = cfg_get("topics", [])
    if not topics:
        return ""

    best_topic = ""
    best_overlap = 0
    text_words = set(text.split())

    for topic in topics:
        topic_str = str(topic).lower()
        topic_words = set(topic_str.split())
        overlap = len(topic_words & text_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_topic = str(topic)

    return best_topic if best_overlap > 0 else ""
