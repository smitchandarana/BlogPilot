from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.storage.models import Budget
from backend.utils.logger import get_logger

logger = get_logger(__name__)


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
    for row in rows:
        row.count_today = 0
        row.last_reset_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Daily budget counters reset")


def get_all(db: Session) -> list:
    return db.query(Budget).all()
