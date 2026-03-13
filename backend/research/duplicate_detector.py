"""
Duplicate post detector — prevents publishing identical or near-identical content.

Uses SHA256 content hashing on normalized text to detect exact and near-exact duplicates.
"""
import hashlib
import re
import unicodedata

from backend.storage.models import PostContentHash, ScheduledPost
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def normalize_text(text: str) -> str:
    """Normalize text for hashing: lowercase, strip whitespace/hashtags/emojis/punctuation."""
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove hashtags (e.g. #analytics)
    text = re.sub(r"#\w+", "", text)
    # Remove emoji (unicode emoji ranges)
    text = _strip_emoji(text)
    # Remove punctuation except apostrophes in contractions
    text = re.sub(r"[^\w\s']", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _strip_emoji(text: str) -> str:
    """Remove emoji and other non-text unicode characters."""
    return "".join(
        ch for ch in text
        if unicodedata.category(ch) not in ("So", "Sk", "Sc", "Sm", "Cn")
        or ch in ("'", "'")
    )


def compute_hash(text: str) -> str:
    """SHA256 hash of normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def check_duplicate(text: str, db) -> dict:
    """
    Check if text is a duplicate of any previously published post.

    Returns:
        {is_duplicate: bool, similarity: float, matching_preview: str|None}
    """
    content_hash = compute_hash(text)

    # Check content hash table
    existing = (
        db.query(PostContentHash)
        .filter_by(content_hash=content_hash)
        .first()
    )
    if existing:
        logger.info(f"DuplicateDetector: exact hash match found (post_id={existing.post_id})")
        return {
            "is_duplicate": True,
            "similarity": 1.0,
            "matching_preview": existing.text_preview,
        }

    # Check scheduled_posts for exact text match (covers posts not yet hash-registered)
    normalized = normalize_text(text)
    published = (
        db.query(ScheduledPost)
        .filter(ScheduledPost.status.in_(["PUBLISHED", "SCHEDULED"]))
        .all()
    )
    for post in published:
        if normalize_text(post.text or "") == normalized:
            logger.info(f"DuplicateDetector: exact text match in scheduled_posts (id={post.id})")
            return {
                "is_duplicate": True,
                "similarity": 1.0,
                "matching_preview": (post.text or "")[:500],
            }

    return {"is_duplicate": False, "similarity": 0.0, "matching_preview": None}


def register_post(text: str, post_id: str, db) -> None:
    """Register a published post's content hash for future duplicate detection."""
    content_hash = compute_hash(text)

    existing = db.query(PostContentHash).filter_by(content_hash=content_hash).first()
    if existing:
        logger.debug(f"DuplicateDetector: hash already registered for post {existing.post_id}")
        return

    record = PostContentHash(
        content_hash=content_hash,
        post_id=post_id,
        text_preview=(text or "")[:500],
    )
    db.add(record)
    db.commit()
    logger.info(f"DuplicateDetector: registered hash for post {post_id}")
