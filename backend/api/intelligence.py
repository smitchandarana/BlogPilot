"""
Content Intelligence API — Sprint 11.

Endpoints:
  GET  /intelligence/insights              — paginated insights with filters
  GET  /intelligence/patterns              — patterns by type
  GET  /intelligence/patterns/for-generation — curated set for a topic
  POST /intelligence/extract               — trigger manual extraction run
  GET  /intelligence/status                — counts, last run, unprocessed count
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.utils.logger import get_logger
from backend.storage.database import get_db
from backend.ai.client_factory import build_ai_client

logger = get_logger(__name__)
router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────

class ExtractTextRequest(BaseModel):
    text: str
    source: str = "MANUAL"


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/insights")
async def list_insights(
    topic: Optional[str] = Query(None),
    hook_type: Optional[str] = Query(None),
    content_style: Optional[str] = Query(None),
    min_score: float = Query(0.0),
    limit: int = Query(50),
    offset: int = Query(0),
):
    """Return paginated content insights with optional filters."""
    from backend.storage.models import ContentInsight

    with get_db() as db:
        q = db.query(ContentInsight)
        if topic:
            q = q.filter(
                ContentInsight.topic.ilike(f"%{topic}%")
                | ContentInsight.subtopic.ilike(f"%{topic}%")
            )
        if hook_type:
            q = q.filter(ContentInsight.hook_type == hook_type.upper())
        if content_style:
            q = q.filter(ContentInsight.content_style == content_style.upper())
        if min_score > 0:
            q = q.filter(ContentInsight.specificity_score >= min_score)

        total = q.count()
        rows = (
            q.order_by(
                ContentInsight.specificity_score.desc(),
                ContentInsight.source_engagement.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "insights": [_serialize_insight(r) for r in rows],
        }


@router.get("/patterns/for-generation")
async def patterns_for_generation(topic: str = Query(...)):
    """
    Return a curated set of patterns and evidence for the given topic.
    Used by the ContentStudio intelligence panel.
    """
    from backend.research.pattern_aggregator import PatternAggregator

    agg = PatternAggregator()
    with get_db() as db:
        return agg.get_for_generation(topic, db)


@router.get("/patterns")
async def list_patterns(
    pattern_type: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    limit: int = Query(20),
):
    """Return content patterns, optionally filtered by type and domain."""
    from backend.storage.models import ContentPattern

    with get_db() as db:
        q = db.query(ContentPattern)
        if pattern_type:
            q = q.filter(ContentPattern.pattern_type == pattern_type.upper())
        if domain:
            q = q.filter(ContentPattern.domain.ilike(f"%{domain}%"))

        rows = (
            q.order_by(
                ContentPattern.frequency.desc(),
                ContentPattern.avg_engagement.desc(),
            )
            .limit(limit)
            .all()
        )
        return [_serialize_pattern(r) for r in rows]


@router.get("/patterns/{pattern_id}")
async def get_pattern_detail(pattern_id: int):
    """Return a single pattern plus its supporting content insights."""
    from backend.storage.models import ContentPattern, ContentInsight

    with get_db() as db:
        pattern = db.query(ContentPattern).filter_by(id=pattern_id).first()
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")

        insight_ids = pattern.example_insight_ids or []
        insights = []
        if insight_ids:
            insights = (
                db.query(ContentInsight)
                .filter(ContentInsight.id.in_(insight_ids))
                .order_by(ContentInsight.specificity_score.desc())
                .all()
            )

        return {
            **_serialize_pattern(pattern),
            "insights": [_serialize_insight(r) for r in insights],
        }


@router.post("/extract")
async def trigger_extraction():
    """
    Manually trigger a content extraction run.
    Processes unprocessed research snippets → ContentInsight rows,
    then refreshes ContentPattern aggregations.
    Uses OpenRouter (background client) — falls back to Groq if no OpenRouter key.
    """
    ai_client, prompt_loader = _build_ai_deps()
    if ai_client is None:
        raise HTTPException(
            status_code=503,
            detail="No AI key configured (OpenRouter or Groq required) — add one in Settings"
        )

    from backend.research.content_extractor import ContentExtractor
    from backend.research.pattern_aggregator import PatternAggregator

    extractor = ContentExtractor(ai_client, prompt_loader)
    agg = PatternAggregator()

    with get_db() as db:
        batch_size = _cfg("content_intelligence.extraction_batch_size", 20)
        insights = await extractor.extract_from_snippets(db, batch_size=int(batch_size))
        pattern_counts = agg.aggregate_patterns(db)

    logger.info(f"Intelligence API: manual extraction complete — {len(insights)} insights")

    try:
        from backend.api.websocket import schedule_broadcast
        schedule_broadcast("extraction_complete", {
            "insights_created": len(insights),
            "patterns": pattern_counts,
        })
    except Exception:
        pass

    return {
        "insights_created": len(insights),
        "patterns": pattern_counts,
    }


@router.post("/extract-text")
async def extract_from_text(body: ExtractTextRequest):
    """
    Extract a structured insight from manually pasted text (a LinkedIn post, article, etc.).
    Stores the result as a ContentInsight with source_type=MANUAL.
    """
    if not body.text or len(body.text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Text must be at least 50 characters")

    ai_client, prompt_loader = _build_ai_deps()
    if ai_client is None:
        raise HTTPException(
            status_code=503,
            detail="No AI key configured (OpenRouter or Groq required) — add one in Settings"
        )

    from backend.research.content_extractor import ContentExtractor
    from backend.research.pattern_aggregator import PatternAggregator

    extractor = ContentExtractor(ai_client, prompt_loader)
    with get_db() as db:
        insight = await extractor.extract_from_raw_text(body.text, source=body.source.upper(), db=db)
        if not insight:
            raise HTTPException(status_code=422, detail="Could not extract structured insight from text")
        # Refresh patterns after manual ingestion
        PatternAggregator().aggregate_patterns(db)

    logger.info(f"Intelligence API: manual extract done — subtopic='{insight.get('subtopic')}' score={insight.get('specificity_score')}")
    return insight


@router.post("/session")
async def log_generation_session(body: dict):
    """
    Record a generation session — called by the UI when a post is generated,
    edited, published, or discarded.
    """
    import uuid
    from backend.storage.models import GenerationSession

    with get_db() as db:
        session = GenerationSession(
            id=str(uuid.uuid4()),
            topic=body.get("topic", ""),
            subtopic=body.get("subtopic", ""),
            audience=body.get("audience", ""),
            pain_point=body.get("pain_point", ""),
            hook_intent=body.get("hook_intent", ""),
            proof_type=body.get("proof_type", ""),
            style=body.get("style", ""),
            tone=body.get("tone", ""),
            generated_text=body.get("generated_text", ""),
            final_text=body.get("final_text", body.get("generated_text", "")),
            quality_score=float(body.get("quality_score", 0)),
            edit_distance_ratio=_compute_edit_ratio(
                body.get("generated_text", ""), body.get("final_text", "")
            ),
            action=body.get("action", "pending"),
        )
        db.add(session)
        db.commit()
        return {"id": session.id}


@router.get("/preferences")
async def get_generation_preferences():
    """
    Return learned generation preferences from past sessions:
    best hook types, typical audiences, pain points that led to published posts.
    """
    from backend.learning.content_preference_learner import ContentPreferenceLearner
    with get_db() as db:
        learner = ContentPreferenceLearner()
        return learner.get_preferences(db)


@router.get("/status")
async def intelligence_status():
    """Return intelligence system counts and last extraction info."""
    from backend.storage.models import ContentInsight, ContentPattern, ResearchSnippet

    with get_db() as db:
        total_insights = db.query(ContentInsight).count()
        total_patterns = db.query(ContentPattern).count()

        try:
            unprocessed = (
                db.query(ResearchSnippet)
                .filter(ResearchSnippet.processed_for_insights == False)  # noqa: E712
                .count()
            )
        except Exception:
            unprocessed = 0

        last_insight = (
            db.query(ContentInsight)
            .order_by(ContentInsight.created_at.desc())
            .first()
        )
        last_extraction = last_insight.created_at.isoformat() if last_insight else None

    return {
        "total_insights": total_insights,
        "total_patterns": total_patterns,
        "unprocessed_snippets": unprocessed,
        "last_extraction": last_extraction,
    }


# ── Internal helpers ──────────────────────────────────────────────────────

def _compute_edit_ratio(original: str, final: str) -> float:
    """Compute normalized edit distance ratio. 0 = identical, 1 = completely different."""
    if not original and not final:
        return 0.0
    if not original or not final:
        return 1.0
    try:
        # Simple character-level similarity
        longer = max(len(original), len(final))
        if longer == 0:
            return 0.0
        # Count character differences using common subsequence length approximation
        orig_words = set(original.lower().split())
        final_words = set(final.lower().split())
        if not orig_words:
            return 1.0
        overlap = len(orig_words & final_words) / len(orig_words | final_words)
        return round(1.0 - overlap, 3)
    except Exception:
        return 0.0


def _cfg(key: str, default=None):
    try:
        from backend.utils.config_loader import get as cfg_get
        return cfg_get(key, default)
    except Exception:
        return default


def _build_ai_deps():
    """Build background AI client + PromptLoader via the client factory."""
    try:
        from backend.ai.prompt_loader import PromptLoader

        ai_client = build_ai_client("background")
        if ai_client is None:
            logger.warning("Intelligence API: no AI key available for background tasks")
            return None, None

        prompt_loader = PromptLoader()
        prompt_loader.load_all()
        return ai_client, prompt_loader
    except Exception as e:
        logger.warning(f"Intelligence API: failed to build AI deps — {e}")
        return None, None


def _serialize_insight(r) -> dict:
    return {
        "id": r.id,
        "snippet_id": r.snippet_id,
        "topic": r.topic,
        "subtopic": r.subtopic,
        "pain_point": r.pain_point,
        "hook_type": r.hook_type,
        "content_style": r.content_style,
        "key_insight": r.key_insight,
        "audience_segment": r.audience_segment,
        "sentiment": r.sentiment,
        "specificity_score": r.specificity_score,
        "source_type": r.source_type,
        "source_engagement": r.source_engagement,
        "times_used_in_generation": r.times_used_in_generation,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _serialize_pattern(r) -> dict:
    return {
        "id": r.id,
        "pattern_type": r.pattern_type,
        "pattern_value": r.pattern_value,
        "frequency": r.frequency,
        "avg_engagement": r.avg_engagement,
        "example_insight_ids": r.example_insight_ids or [],
        "domain": r.domain,
        "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
    }
