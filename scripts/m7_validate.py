"""
M7 Runtime Validation — BlogPilot

Checks all Milestone 7 criteria against the live SQLite database.
Run from the project root:

    python scripts/m7_validate.py

Exit code 0 = all checks pass. Non-zero = failures detected.
"""
import sys
import os
import io
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 output on Windows to handle Unicode symbols
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = "\033[32m[OK]\033[0m"
FAIL = "\033[31m[FAIL]\033[0m"
WARN = "\033[33m[WARN]\033[0m"
INFO = "\033[36m[INFO]\033[0m"

failures = 0
warnings = 0


def ok(label, detail=""):
    print(f"  {PASS}  {label}" + (f"  ({detail})" if detail else ""))


def fail(label, detail=""):
    global failures
    failures += 1
    print(f"  {FAIL}  {label}" + (f"  — {detail}" if detail else ""))


def warn(label, detail=""):
    global warnings
    warnings += 1
    print(f"  {WARN}  {label}" + (f"  — {detail}" if detail else ""))


def info(label, detail=""):
    print(f"  {INFO}  {label}" + (f"  {detail}" if detail else ""))


# ── 1. Database accessible ─────────────────────────────────────────────────
print("\n[ 1 ] Database")
try:
    from backend.storage.database import get_db
    with get_db() as db:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    ok("Database opens cleanly")
except Exception as e:
    fail("Cannot open database", str(e))
    print("\nCannot continue — database is required for all remaining checks.")
    sys.exit(1)


# ── 2. Actions logged today ────────────────────────────────────────────────
print("\n[ 2 ] Actions logged today")
try:
    with get_db() as db:
        from backend.storage.models import ActionLog
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        total_today = (
            db.query(ActionLog)
            .filter(ActionLog.created_at >= today_start)
            .count()
        )
        if total_today > 0:
            ok(f"{total_today} actions logged today")
        else:
            warn("No actions logged today — engine may not have run yet")

        # Break down by type
        from sqlalchemy import func
        breakdown = (
            db.query(ActionLog.action_type, func.count(ActionLog.id))
            .filter(ActionLog.created_at >= today_start)
            .group_by(ActionLog.action_type)
            .all()
        )
        for atype, cnt in breakdown:
            info(f"  {atype}: {cnt}")
except Exception as e:
    fail("Could not query actions_log", str(e))


# ── 3. Budget limits enforced (no budget overruns) ─────────────────────────
print("\n[ 3 ] Budget enforcement")
try:
    with get_db() as db:
        from backend.storage.models import Budget
        budgets = db.query(Budget).all()
        if not budgets:
            warn("No budget rows found — budget tracker may not be initialised")
        else:
            any_exceeded = False
            for b in budgets:
                if b.limit_per_day == 0:
                    continue  # unlimited
                if b.count_today > b.limit_per_day:
                    fail(f"Budget EXCEEDED: {b.action_type} = {b.count_today}/{b.limit_per_day}")
                    any_exceeded = True
                else:
                    pct = int(b.count_today / b.limit_per_day * 100) if b.limit_per_day else 0
                    status = "at limit" if b.count_today >= b.limit_per_day else f"{pct}%"
                    ok(f"{b.action_type}: {b.count_today}/{b.limit_per_day} ({status})")
            if not any_exceeded:
                ok("No budget overruns detected")
except Exception as e:
    fail("Could not query budget table", str(e))


# ── 4. Midnight reset ran (budget counts are daily, not cumulative) ────────
print("\n[ 4 ] Midnight reset")
try:
    with get_db() as db:
        from backend.storage.models import Budget
        budgets = db.query(Budget).all()
        if budgets:
            # All counts should be <= daily_limit; if any are wildly high it suggests no reset
            max_count = max((b.count_today for b in budgets if b.limit_per_day > 0), default=0)
            max_limit = max((b.limit_per_day for b in budgets if b.limit_per_day > 0), default=1)
            if max_count > max_limit * 3:
                warn(
                    "Some counts are >3× the daily limit — midnight reset may not be running",
                    f"max count_today={max_count}",
                )
            else:
                ok("Budget counts within expected range (reset appears to be working)")
        else:
            warn("No budget rows to validate reset against")
except Exception as e:
    fail("Could not validate midnight reset", str(e))


# ── 5. Posts scanned (feed scanner ran) ────────────────────────────────────
print("\n[ 5 ] Feed scan activity")
try:
    with get_db() as db:
        from backend.storage.models import Post
        total_posts = db.query(Post).count()
        last_7d = datetime.utcnow() - timedelta(days=7)
        recent_posts = db.query(Post).filter(Post.created_at >= last_7d).count()
        if total_posts == 0:
            warn("No posts in database — engine may never have run a feed scan")
        elif recent_posts == 0:
            warn(f"No posts scanned in the last 7 days (total all-time: {total_posts})")
        else:
            ok(f"{recent_posts} posts scanned in last 7 days (total: {total_posts})")

        # Posts by state
        from sqlalchemy import func
        by_state = (
            db.query(Post.state, func.count(Post.id))
            .group_by(Post.state)
            .all()
        )
        for state, cnt in by_state:
            info(f"  state={state}: {cnt}")
except Exception as e:
    fail("Could not query posts table", str(e))


# ── 6. Circuit breaker not permanently tripped ─────────────────────────────
print("\n[ 6 ] Circuit breaker")
try:
    from backend.core.engine import get_engine
    engine = get_engine()
    if engine is None:
        warn("Engine not running — cannot check circuit breaker live state")
    else:
        cb = engine.circuit_breaker
        if cb.is_open():
            warn("Circuit breaker is currently TRIPPED — engine is paused")
        else:
            ok("Circuit breaker is not tripped")
except Exception as e:
    warn("Could not check circuit breaker (engine may not be running)", str(e))

# Also check logs for recent circuit breaker events
try:
    log_path = Path("logs/engine.log")
    if log_path.exists():
        with open(log_path, "r", errors="replace") as f:
            lines = f.readlines()
        cb_lines = [l for l in lines[-500:] if "circuit" in l.lower() or "tripped" in l.lower()]
        if cb_lines:
            info(f"Recent circuit breaker log entries ({len(cb_lines)}):")
            for l in cb_lines[-3:]:
                info("  " + l.strip()[:120])
        else:
            ok("No circuit breaker events in last 500 log lines")
except Exception:
    pass


# ── 7. Error rate (no error spike in logs) ────────────────────────────────
print("\n[ 7 ] Error rate (last 500 log lines)")
try:
    log_path = Path("logs/engine.log")
    if not log_path.exists():
        warn("No log file found at logs/engine.log")
    else:
        with open(log_path, "r", errors="replace") as f:
            lines = f.readlines()
        last_lines = lines[-500:]
        error_lines = [l for l in last_lines if '"level": "ERROR"' in l or " ERROR " in l]
        warning_lines = [l for l in last_lines if '"level": "WARNING"' in l or " WARNING " in l]
        error_rate = len(error_lines) / len(last_lines) if last_lines else 0

        if error_rate > 0.20:
            fail(
                f"High error rate: {len(error_lines)}/{len(last_lines)} lines are errors ({error_rate:.0%})",
                "Check logs/engine.log for details",
            )
        elif error_rate > 0.05:
            warn(
                f"Moderate errors: {len(error_lines)}/{len(last_lines)} lines ({error_rate:.0%})",
            )
        else:
            ok(f"Error rate acceptable: {len(error_lines)} errors, {len(warning_lines)} warnings in last 500 lines")

        # Show last 3 errors
        if error_lines:
            info("Last errors:")
            for l in error_lines[-3:]:
                info("  " + l.strip()[:120])
except Exception as e:
    fail("Could not analyse log file", str(e))


# ── 8. Analytics queries return data ──────────────────────────────────────
print("\n[ 8 ] Analytics queries")
try:
    with get_db() as db:
        from backend.storage.models import ActionLog, Post, Budget
        from sqlalchemy import func

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Daily stats
        daily_count = db.query(func.count(ActionLog.id)).filter(ActionLog.created_at >= today_start).scalar()
        ok(f"Daily actions query: {daily_count} rows")

        # Weekly stats
        week_start = datetime.utcnow() - timedelta(days=7)
        weekly_count = db.query(func.count(ActionLog.id)).filter(ActionLog.created_at >= week_start).scalar()
        ok(f"Weekly actions query: {weekly_count} rows")

        # Top topics
        from backend.storage.models import TopicPerformance
        topic_count = db.query(func.count(TopicPerformance.id)).scalar()
        ok(f"Topic performance table: {topic_count} rows")

        # Scheduled posts
        from backend.storage.models import ScheduledPost
        sched_count = db.query(func.count(ScheduledPost.id)).scalar()
        ok(f"Scheduled posts table: {sched_count} rows")
except Exception as e:
    fail("Analytics query failed", str(e))


# ── 9. Content intelligence (optional, not required for M7) ───────────────
print("\n[ 9 ] Content intelligence (informational)")
try:
    with get_db() as db:
        from backend.storage.models import ContentInsight, ContentPattern
        insight_count = db.query(ContentInsight).count()
        pattern_count = db.query(ContentPattern).count()
        info(f"ContentInsights: {insight_count}, ContentPatterns: {pattern_count}")

        from backend.storage.models import GenerationSession
        session_count = db.query(GenerationSession).count()
        published_count = db.query(GenerationSession).filter_by(action="published").count()
        info(f"GenerationSessions: {session_count} total, {published_count} published")
except Exception as e:
    info(f"Content intelligence tables not queryable: {e}")


# ── Summary ───────────────────────────────────────────────────────────────
print()
print("─" * 50)
if failures == 0 and warnings == 0:
    print(f"{PASS}  All M7 checks passed. Ready for production run.")
elif failures == 0:
    print(f"{WARN}  {warnings} warning(s), 0 failures. Review warnings before long run.")
else:
    print(f"{FAIL}  {failures} failure(s), {warnings} warning(s). Fix failures before M7 validation.")

print("─" * 50)
sys.exit(failures)
