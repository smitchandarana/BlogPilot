"""
Auto-tuner — Phase D1.

Automatically adjusts scoring thresholds and activity schedule
based on accumulated engagement data.

Runs every 24h via IntervalTrigger (not CronTrigger) so it's relative
to engine start, not wall clock. Also runs on engine start if stale
(same pattern as budget reset_if_stale).
"""
import os
import json
from datetime import datetime, timezone, timedelta

from backend.utils.config_loader import get as cfg_get, save_config
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_TUNE_STATE_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "auto_tune_state.json")
)


def _load_state() -> dict:
    """Load the auto-tune state file."""
    try:
        if os.path.exists(_TUNE_STATE_FILE):
            with open(_TUNE_STATE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_state(state: dict):
    """Save the auto-tune state file."""
    try:
        os.makedirs(os.path.dirname(_TUNE_STATE_FILE), exist_ok=True)
        with open(_TUNE_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"AutoTuner: could not save state: {e}")


def tune_if_stale(db):
    """
    Check if last tune was >24h ago and run if so.
    Called from engine.start() — same pattern as budget reset_if_stale.
    """
    if not cfg_get("learning.auto_tune_enabled", False):
        return

    state = _load_state()
    last_tune_str = state.get("last_tune_at")

    if last_tune_str:
        try:
            last_tune = datetime.fromisoformat(last_tune_str)
            if last_tune.tzinfo is None:
                last_tune = last_tune.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_tune < timedelta(hours=24):
                return  # Not stale yet
        except Exception:
            pass

    logger.info("AutoTuner: stale (>24h since last tune) — running now")
    run_auto_tune(db)


def run_auto_tune(db=None):
    """
    Main auto-tuning logic. Adjusts settings based on engagement data.
    """
    if not cfg_get("learning.auto_tune_enabled", False):
        logger.info("AutoTuner: disabled in config — skipping")
        return

    if db is None:
        from backend.storage.database import get_db
        with get_db() as db:
            return _do_tune(db)
    else:
        return _do_tune(db)


def _do_tune(db):
    """Execute tuning logic."""
    changes = {}

    try:
        # ── Tune scoring threshold ──
        score_change = _tune_scoring_threshold(db)
        if score_change:
            changes.update(score_change)

        # ── Tune activity schedule ──
        schedule_change = _tune_schedule(db)
        if schedule_change:
            changes.update(schedule_change)

        # Apply changes
        if changes:
            save_config(changes)
            logger.info(f"AutoTuner: applied changes: {changes}")
        else:
            logger.info("AutoTuner: no adjustments needed")

        # Update state
        state = _load_state()
        state["last_tune_at"] = datetime.now(timezone.utc).isoformat()
        state["last_changes"] = changes
        _save_state(state)

    except Exception as e:
        logger.error(f"AutoTuner: tuning failed: {e}")


def _tune_scoring_threshold(db) -> dict:
    """
    Adjust min_relevance_score based on score-to-engagement calibration.
    Changes by at most ±0.5 per cycle, bounded by config min/max.
    Requires min_posts data points.
    """
    from backend.storage.models import Post

    min_posts = int(cfg_get("learning.auto_tune_min_posts", 50))
    threshold_min = float(cfg_get("learning.scoring_threshold_min", 4.0))
    threshold_max = float(cfg_get("learning.scoring_threshold_max", 9.0))
    max_change = float(cfg_get("learning.scoring_threshold_max_change", 0.5))

    # Count scored posts
    total_scored = (
        db.query(Post)
        .filter(Post.relevance_score.isnot(None))
        .count()
    )
    if total_scored < min_posts:
        logger.info(
            f"AutoTuner: only {total_scored}/{min_posts} scored posts — "
            f"skipping threshold adjustment"
        )
        return {}

    current_threshold = float(cfg_get("feed_engagement.min_relevance_score", 6))

    # Count acted vs scored in the current threshold bucket (threshold ± 1)
    from backend.learning.scoring_calibrator import scoring_calibrator
    data = scoring_calibrator.analyze(db)
    optimal = data.get("optimal_min_score", current_threshold)

    # Limit change to ±max_change per cycle
    delta = optimal - current_threshold
    if abs(delta) > max_change:
        delta = max_change if delta > 0 else -max_change

    new_threshold = round(current_threshold + delta, 1)
    new_threshold = max(threshold_min, min(threshold_max, new_threshold))

    if new_threshold != current_threshold:
        logger.info(
            f"AutoTuner: adjusting min_relevance_score "
            f"{current_threshold} → {new_threshold}"
        )
        return {"feed_engagement": {"min_relevance_score": new_threshold}}

    return {}


def _tune_schedule(db) -> dict:
    """
    Narrow start_hour/end_hour to exclude consistently low-engagement hours.
    Only adjusts if there's clear evidence (>20 actions in the dataset).
    """
    from backend.learning.timing_analyzer import timing_analyzer

    data = timing_analyzer.analyze(db)
    if data["total_actions"] < 20:
        return {}

    best_hours = data.get("best_hours", [])
    if len(best_hours) < 2:
        return {}

    current_start = int(cfg_get("schedule.start_hour", 9))
    current_end = int(cfg_get("schedule.end_hour", 23))

    # Suggest narrowing to the range of best hours ± 1
    suggested_start = max(min(best_hours) - 1, 6)  # never before 6 AM
    suggested_end = min(max(best_hours) + 2, 23)  # never after 23

    changes = {}
    # Only narrow, never widen
    if suggested_start > current_start:
        changes.setdefault("schedule", {})["start_hour"] = suggested_start
    if suggested_end < current_end:
        changes.setdefault("schedule", {})["end_hour"] = suggested_end

    if changes:
        logger.info(
            f"AutoTuner: suggesting schedule adjustment — "
            f"start={changes.get('schedule', {}).get('start_hour', current_start)}, "
            f"end={changes.get('schedule', {}).get('end_hour', current_end)}"
        )

    return changes


def job_auto_tune():
    """Sync entry point for scheduler."""
    logger.info("AutoTuner: scheduled tune starting")
    try:
        from backend.storage.database import get_db
        with get_db() as db:
            run_auto_tune(db)
    except Exception as e:
        logger.warning(f"AutoTuner: scheduled tune failed: {e}")
