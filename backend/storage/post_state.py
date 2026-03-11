from typing import Optional, List
from sqlalchemy.orm import Session

from backend.storage.models import Post
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def is_seen(url: str, db: Session) -> bool:
    return db.query(Post.id).filter_by(url=url).first() is not None


def mark_seen(url: str, db: Session, **kwargs) -> Post:
    post = db.query(Post).filter_by(url=url).first()
    if post:
        return post
    post = Post(url=url, state="SEEN", **kwargs)
    db.add(post)
    db.commit()
    db.refresh(post)
    logger.debug(f"Post marked SEEN: {url[:80]}")
    return post


def update_state(url: str, state: str, db: Session, **kwargs) -> Optional[Post]:
    post = db.query(Post).filter_by(url=url).first()
    if not post:
        logger.warning(f"update_state: Post not found for URL {url[:80]}")
        return None
    post.state = state
    for k, v in kwargs.items():
        setattr(post, k, v)
    db.commit()
    db.refresh(post)
    return post


def get_recent_posts(limit: int, db: Session) -> List[Post]:
    return (
        db.query(Post)
        .order_by(Post.created_at.desc())
        .limit(limit)
        .all()
    )
