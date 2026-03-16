from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.storage.models import Budget, ActionLog
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _utcnow_naive():
    """Return current UTC time as a naive datetime (for SQLite compatibility)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def check(action_type: str, db: Session) -> bool:
    row = db.query(Budget).filter_by(action_type=action_type).first()
    if not row:
        logger.warning(f"Budget row missing for action_type={action_type} — allowing")
        return True
    if row.limit_per_day == 0:
        return True  # 0 = unlimited
    allowed = row.count_today < row.limit_per_day
    if not allowed:
        logger.info(f"Budget exhausted for {action_type}: {row.count_today}/{row.limit_per_day}")
    return allowed


def increment(action_type: str, db: Session):
    row = db.query(Budget).filter_by(action_type=action_type).first()
    if row:
        row.count_today += 1
        db.commit()
        logger.debug(f"Budget incremented: {action_type} → {row.count_today}/{row.limit_per_day}")
    else:
        logger.warning(f"Budget row missing for {action_type} — skipping increment")


def reset_all(db: Session):
    rows = db.query(Budget).all()
    now = _utcnow_naive()
    for row in rows:
        row.count_today = 0
        row.last_reset_at = now
    db.commit()
    logger.info("Daily budget counters reset")


def reset_if_stale(db: Session):
    """Reset budget if last reset was before today (handles missed midnight resets)."""
    row = db.query(Budget).first()
    if not row or not row.last_reset_at:
        return
    # SQLite stores naive datetimes (UTC), so compare naive-to-naive
    reset_date = row.last_reset_at.date()
    today_utc = _utcnow_naive().date()
    if reset_date < today_utc:
        logger.info(f"Budget stale (last reset {reset_date}, today {today_utc}) — resetting now")
        reset_all(db)


def sync_from_actions(db: Session):
    """Rebuild budget count_today from today's ActionLog entries.

    Fixes desync caused by process crashes, stale resets, or missed increments.
    """
    today_start = _utcnow_naive().replace(hour=0, minute=0, second=0, microsecond=0)

    counts = (
        db.query(ActionLog.action_type, func.count(ActionLog.id))
        .filter(ActionLog.result == "SUCCESS")
        .filter(ActionLog.created_at >= today_start)
        .group_by(ActionLog.action_type)
        .all()
    )
    count_map = dict(counts)

    rows = db.query(Budget).all()
    changed = False
    for row in rows:
        actual = count_map.get(row.action_type, 0)
        if row.count_today != actual:
            logger.info(f"Budget sync: {row.action_type} count_today {row.count_today} → {actual}")
            row.count_today = actual
            changed = True
    if changed:
        db.commit()
        logger.info("Budget counts synced from ActionLog")
    else:
        logger.debug("Budget counts already in sync with ActionLog")


def get_all(db: Session) -> list:
    return db.query(Budget).all()
