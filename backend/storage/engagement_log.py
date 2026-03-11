from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.storage.models import ActionLog
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def write_action(
    action_type: str,
    target_url: str,
    target_name: str,
    result: str,
    db: Session,
    comment_text: Optional[str] = None,
    error_msg: Optional[str] = None,
    topic_tag: Optional[str] = None,
) -> ActionLog:
    entry = ActionLog(
        action_type=action_type,
        target_url=target_url,
        target_name=target_name,
        result=result,
        comment_text=comment_text,
        error_msg=error_msg,
        topic_tag=topic_tag,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.debug(f"Action logged: {action_type} → {result} on {target_name}")
    return entry


def get_recent(n: int, db: Session) -> List[ActionLog]:
    return (
        db.query(ActionLog)
        .order_by(ActionLog.created_at.desc())
        .limit(n)
        .all()
    )


def get_stats_today(db: Session) -> dict:
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    rows = (
        db.query(ActionLog.action_type, func.count(ActionLog.id))
        .filter(ActionLog.created_at >= today_start)
        .group_by(ActionLog.action_type)
        .all()
    )
    return {row[0]: row[1] for row in rows}
