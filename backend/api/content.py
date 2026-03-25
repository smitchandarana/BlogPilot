"""
Content Studio API — Sprint 7.

Endpoints for the ContentStudio page:
  POST /content/schedule     — queue a post for publishing at a future time
  POST /content/publish-now  — publish immediately via browser
  GET  /content/queue        — list all scheduled/published posts
  DELETE /content/queue/{id} — cancel a scheduled post
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.utils.logger import get_logger
from backend.storage.database import get_db
from backend.storage.models import ScheduledPost
from backend.ai.client_factory import build_ai_client, AIClientUnavailableError

logger = get_logger(__name__)
router = APIRouter()


# ── Request / response models ─────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    text: str
    topic: Optional[str] = None
    style: Optional[str] = None
    tone: Optional[str] = None
    scheduled_at: str  # ISO 8601 string, e.g. "2025-06-01T09:00:00"


class PublishNowRequest(BaseModel):
    text: str
    topic: Optional[str] = None
    style: Optional[str] = None


class StructuredGenerateRequest(BaseModel):
    topic: str
    subtopic: Optional[str] = None
    pain_point: Optional[str] = None
    audience: Optional[str] = None
    hook_intent: Optional[str] = None      # CONTRARIAN | QUESTION | STAT | STORY | TREND | MISTAKE
    belief_to_challenge: Optional[str] = None
    core_insight: Optional[str] = None
    proof_type: Optional[str] = None       # STAT | STORY | EXAMPLE | ANALOGY | FRAMEWORK
    real_scenario: Optional[str] = None    # Concrete role + situation anchor for generation
    style: str = "Thought Leadership"
    tone: str = "Professional"
    word_count: int = 150
    style_examples: Optional[list] = None  # Top published posts for style matching


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/queue")
async def get_post_queue():
    """Return all posts in the schedule queue (any status)."""
    with get_db() as db:
        posts = (
            db.query(ScheduledPost)
            .order_by(ScheduledPost.scheduled_at.asc())
            .all()
        )
        return [_serialize(p) for p in posts]


@router.post("/schedule")
async def schedule_post(body: ScheduleRequest, force: bool = Query(False)):
    """Add a post to the publishing queue at the given scheduled_at time."""
    try:
        scheduled_at = datetime.fromisoformat(body.scheduled_at)
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid scheduled_at format — use ISO 8601")

    # Duplicate detection
    if not force:
        try:
            from backend.research.duplicate_detector import check_duplicate
            with get_db() as db:
                dup = check_duplicate(body.text, db)
                if dup["is_duplicate"]:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": "Near-duplicate post detected",
                            "similarity": dup["similarity"],
                            "matching_preview": dup["matching_preview"],
                        },
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # Don't block on duplicate check failure

    with get_db() as db:
        post = ScheduledPost(
            id=str(uuid.uuid4()),
            text=body.text,
            topic=body.topic,
            style=body.style,
            tone=body.tone,
            status="SCHEDULED",
            scheduled_at=scheduled_at,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        logger.info(f"Content: post scheduled for {scheduled_at.isoformat()}")
        return _serialize(post)


@router.delete("/queue/{post_id}")
async def cancel_post(post_id: str):
    """Cancel a scheduled post (only if still in SCHEDULED status)."""
    with get_db() as db:
        post = db.query(ScheduledPost).filter_by(id=post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        if post.status != "SCHEDULED":
            raise HTTPException(
                status_code=409,
                detail=f"Cannot cancel post with status '{post.status}'"
            )
        post.status = "CANCELLED"
        db.commit()
        logger.info(f"Content: post {post_id} cancelled")
        return {"cancelled": post_id}


@router.post("/publish-now")
async def publish_now(body: PublishNowRequest, force: bool = Query(False)):
    """
    Immediately publish a post via the LinkedIn browser session.
    This runs synchronously (via asyncio) — may take 10-30 seconds.
    """
    from backend.core.engine import get_engine
    from backend.core.state_manager import EngineState

    engine = get_engine()
    if not engine or engine.state_manager.get() != EngineState.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Engine must be RUNNING to publish a post"
        )

    # Duplicate detection
    if not force:
        try:
            from backend.research.duplicate_detector import check_duplicate
            with get_db() as db:
                dup = check_duplicate(body.text, db)
                if dup["is_duplicate"]:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "message": "Near-duplicate post detected",
                            "similarity": dup["similarity"],
                            "matching_preview": dup["matching_preview"],
                        },
                    )
        except HTTPException:
            raise
        except Exception:
            pass

    # Record the post in DB as a scheduled post with now as scheduled_at
    with get_db() as db:
        post = ScheduledPost(
            id=str(uuid.uuid4()),
            text=body.text,
            topic=body.topic,
            style=body.style,
            status="SCHEDULED",
            scheduled_at=datetime.now(timezone.utc),
        )
        db.add(post)
        db.commit()
        post_id = post.id

    # Submit to worker pool so it runs off the request thread
    engine.worker_pool.submit(_publish_single, post_id, body.text)
    logger.info(f"Content: publish-now submitted for post {post_id}")
    return {"status": "queued", "post_id": post_id}


@router.post("/generate-structured")
async def generate_structured_post(body: StructuredGenerateRequest):
    """
    Generate a LinkedIn post from structured inputs + content intelligence evidence.
    Returns same shape as existing generation endpoints.
    """
    # Build AI deps
    try:
        from backend.ai.prompt_loader import PromptLoader

        groq_client = build_ai_client("generation")
        prompt_loader = PromptLoader()
        prompt_loader.load_all()
    except AIClientUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Content generate-structured: failed to build AI deps — {e}")
        raise HTTPException(status_code=503, detail=f"AI setup failed: {e}")

    # Fetch evidence from intelligence layer
    evidence = ""
    try:
        from backend.research.pattern_aggregator import PatternAggregator
        agg = PatternAggregator()
        with get_db() as db:
            evidence = agg.get_evidence_block(
                body.topic, db, limit=5, subtopic=body.subtopic or ""
            )
    except Exception as e:
        logger.warning(f"Content generate-structured: evidence fetch failed — {e}")

    # Generate post
    from backend.ai import post_generator
    structured_inputs = {
        "topic": body.topic,
        "subtopic": body.subtopic or body.topic,
        "pain_point": body.pain_point or "",
        "audience": body.audience or "",
        "hook_intent": body.hook_intent or "STORY",
        "core_insight": body.core_insight or "",
        "belief_to_challenge": body.belief_to_challenge or "",
        "proof_type": body.proof_type or "EXAMPLE",
        "real_scenario": body.real_scenario or "",
        "style": body.style,
        "tone": body.tone,
        "word_count": body.word_count,
    }

    result = await post_generator.generate_structured(
        structured_inputs=structured_inputs,
        groq_client=groq_client,
        prompt_loader=prompt_loader,
        evidence=evidence,
        style_examples=body.style_examples or None,
    )
    return result


class IdeaPoolItem(BaseModel):
    id: str
    source_type: str
    title: Optional[str] = None
    text: str
    url: Optional[str] = None
    date: Optional[str] = None
    engagement_score: float = 0.0


class HighlightItem(BaseModel):
    text: str
    tag: str  # Hook | Stat | Story | Insight | Example


class SelectionItem(BaseModel):
    id: str
    source_type: str
    full_text: str
    highlights: list[HighlightItem] = []


class SynthesizeBriefRequest(BaseModel):
    selections: list[SelectionItem]


class GenerateFromBriefRequest(BaseModel):
    brief: str
    topic: str = "Business Intelligence"
    style: str = "Thought Leadership"
    tone: str = "Professional"
    word_count: int = 150


class PipelineGenerateRequest(BaseModel):
    topic: str
    style: str = "Thought Leadership"
    tone: str = "Professional"
    word_count: int = 150
    insight_id: Optional[int] = None


@router.post("/generate-v2")
async def generate_pipeline_post(req: PipelineGenerateRequest):
    """
    3-call pipeline: ContentInsight → angle → post → score.
    Falls back to generate_structured() if no insight found for topic.
    """
    from backend.storage.budget_tracker import BudgetTracker
    with get_db() as db:
        budget = BudgetTracker()
        if not budget.check("structured_generation", db):
            raise HTTPException(
                status_code=429,
                detail="Daily generation limit reached (10/day). Try again tomorrow."
            )

        try:
            groq_client = build_ai_client("generation")
        except AIClientUnavailableError as e:
            raise HTTPException(status_code=503, detail=str(e))

        prompt_loader = _get_prompt_loader()

        from backend.ai.post_generator import generate_pipeline
        result = await generate_pipeline(
            topic=req.topic,
            style=req.style,
            tone=req.tone,
            word_count=req.word_count,
            groq_client=groq_client,
            prompt_loader=prompt_loader,
            db=db,
            insight_id=req.insight_id,
        )

        budget.increment("structured_generation", db)
    return result


@router.get("/idea-pool")
async def get_idea_pool(
    q: Optional[str] = Query(None),
    source: str = Query("all"),
    topic: Optional[str] = Query(None),
    limit: int = Query(30),
    offset: int = Query(0),
):
    """
    Return a unified, normalized list of content items for the Ideas Lab.
    Sources: linkedin (posts table), reddit/rss/hn (research_snippets), my_posts (scheduled_posts).
    Ranked by keyword overlap with `topic` if provided, otherwise by recency.
    """
    from backend.storage.models import Post, ResearchSnippet, ScheduledPost

    items = []

    with get_db() as db:
        # ── LinkedIn posts ──────────────────────────────────────────────
        if source in ("all", "linkedin"):
            rows = db.query(Post).filter(Post.text.isnot(None)).order_by(
                Post.created_at.desc()
            ).limit(200).all()
            for r in rows:
                items.append({
                    "id": f"li_{r.id}",
                    "source_type": "LINKEDIN",
                    "title": r.author_name,
                    "text": r.text or "",
                    "url": r.url,
                    "date": r.created_at.isoformat() if r.created_at else None,
                    "engagement_score": float((r.like_count or 0) + (r.comment_count or 0) * 2),
                })

        # ── Research snippets (Reddit / RSS / HN) ───────────────────────
        if source in ("all", "reddit", "rss", "hn"):
            source_filter = None
            if source == "reddit":
                source_filter = "REDDIT"
            elif source == "rss":
                source_filter = "RSS"
            elif source == "hn":
                source_filter = "HN"

            q_snippets = db.query(ResearchSnippet).filter(
                ResearchSnippet.snippet.isnot(None)
            )
            if source_filter:
                q_snippets = q_snippets.filter(
                    ResearchSnippet.source == source_filter
                )
            rows = q_snippets.order_by(
                ResearchSnippet.engagement_signal.desc()
            ).limit(200).all()
            for r in rows:
                items.append({
                    "id": f"rs_{r.id}",
                    "source_type": r.source or "RSS",
                    "title": r.title,
                    "text": r.snippet or "",
                    "url": r.source_url,
                    "date": r.discovered_at.isoformat() if r.discovered_at else None,
                    "engagement_score": float(r.engagement_signal or 0),
                })

        # ── My generated/published posts ────────────────────────────────
        if source in ("all", "my_posts"):
            rows = db.query(ScheduledPost).filter(
                ScheduledPost.status.in_(["PUBLISHED", "SCHEDULED"])
            ).order_by(ScheduledPost.created_at.desc()).limit(100).all()
            for r in rows:
                items.append({
                    "id": f"sp_{r.id}",
                    "source_type": "MY_POST",
                    "title": r.topic,
                    "text": r.text or "",
                    "url": None,
                    "date": r.created_at.isoformat() if r.created_at else None,
                    "engagement_score": 0.0,
                })

    # ── Keyword search ──────────────────────────────────────────────────
    if q:
        q_lower = q.lower()
        items = [
            i for i in items
            if q_lower in (i["text"] or "").lower()
            or q_lower in (i["title"] or "").lower()
        ]

    # ── Topic relevance ranking ─────────────────────────────────────────
    if topic:
        topic_tokens = set(topic.lower().split())

        def _score(item):
            combined = f"{item.get('title', '') or ''} {item.get('text', '') or ''}".lower()
            return sum(1 for t in topic_tokens if t in combined)

        items.sort(key=_score, reverse=True)

    # Pagination
    page = items[offset: offset + limit]
    return page


@router.post("/synthesize-brief")
async def synthesize_brief(body: SynthesizeBriefRequest):
    """
    Call Groq to assemble a synthesis brief from pinned posts + tagged highlights.
    If highlights exist for a selection, they are used. Otherwise falls back to
    first 300 chars of full_text.
    """
    if not body.selections:
        raise HTTPException(status_code=422, detail="At least one selection is required")

    try:
        from backend.ai.prompt_loader import PromptLoader
        groq_client = build_ai_client("generation")
        prompt_loader = PromptLoader()
        prompt_loader.load_all()
    except AIClientUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI setup failed: {e}")

    # Build materials block
    materials_parts = []
    for i, sel in enumerate(body.selections, 1):
        source_label = sel.source_type.replace("_", " ").title()
        if sel.highlights:
            tagged_lines = "\n".join(
                f"  [{h.tag.upper()}] {h.text}" for h in sel.highlights
            )
            materials_parts.append(
                f"Source {i} ({source_label}) — tagged excerpts:\n{tagged_lines}"
            )
        else:
            fallback = (sel.full_text or "")[:300]
            materials_parts.append(
                f"Source {i} ({source_label}) — full text excerpt:\n  {fallback}"
            )

    materials_block = "\n\n".join(materials_parts)

    try:
        prompt = prompt_loader.format(
            "synthesize_brief",
            source_count=len(body.selections),
            materials=materials_block,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt formatting failed: {e}")

    _system = (
        "You are a LinkedIn content strategist. "
        "Return ONLY the synthesis brief. No preamble. No markdown."
    )

    try:
        brief = await groq_client.complete(_system, prompt)
        return {"brief": brief.strip()}
    except Exception as e:
        logger.error(f"synthesize-brief: Groq call failed — {e}")
        raise HTTPException(status_code=503, detail=f"AI call failed: {e}")


@router.post("/generate-from-brief")
async def generate_from_brief(body: GenerateFromBriefRequest):
    """
    Generate a LinkedIn post from a synthesis brief.
    Injects the brief as core_insight into the existing structured_post prompt.
    """
    if not body.brief or not body.brief.strip():
        raise HTTPException(status_code=422, detail="Brief cannot be empty")

    try:
        from backend.ai.prompt_loader import PromptLoader
        groq_client = build_ai_client("generation")
        prompt_loader = PromptLoader()
        prompt_loader.load_all()
    except AIClientUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI setup failed: {e}")

    from backend.ai import post_generator
    topic = body.topic or "Business Intelligence"
    structured_inputs = {
        "topic": topic,
        "subtopic": topic,
        "pain_point": "",
        "audience": "",
        "hook_intent": "STORY",
        "core_insight": body.brief,
        "belief_to_challenge": "",
        "proof_type": "EXAMPLE",
        "real_scenario": "",
        "style": body.style,
        "tone": body.tone,
        "word_count": body.word_count,
    }

    result = await post_generator.generate_structured(
        structured_inputs=structured_inputs,
        groq_client=groq_client,
        prompt_loader=prompt_loader,
        evidence="",
    )
    return result


# ── Internal helpers ──────────────────────────────────────────────────────


def _get_prompt_loader():
    """Return a loaded PromptLoader instance."""
    from backend.ai.prompt_loader import PromptLoader
    loader = PromptLoader()
    loader.load_all()
    return loader

def _serialize(post: ScheduledPost) -> dict:
    return {
        "id": post.id,
        "text": post.text,
        "topic": post.topic,
        "style": post.style,
        "tone": post.tone,
        "status": post.status,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "error_msg": post.error_msg,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


def _publish_single(post_id: str, text: str) -> None:
    """Sync wrapper — called by worker pool to publish one post."""
    import asyncio
    try:
        asyncio.run(_async_publish(post_id, text))
    except Exception as e:
        logger.error(f"Content: publish_single failed — {e}", exc_info=True)


async def _async_publish(post_id: str, text: str) -> None:
    """Async: open browser, login, publish, update DB."""
    from backend.automation.browser import BrowserManager
    from backend.automation.linkedin_login import LinkedInLogin
    from backend.automation.post_publisher import PostPublisher
    from backend.storage.database import get_db as _get_db

    browser = BrowserManager()
    try:
        await browser.launch()
        page = await browser.get_page()

        login = LinkedInLogin()
        if not await login.is_logged_in(page):
            ok = await login.login(page)
            if not ok:
                _mark_failed(post_id, "Login failed")
                return

        publisher = PostPublisher()
        success = await publisher.publish(page, text)

        with _get_db() as db:
            post = db.query(ScheduledPost).filter_by(id=post_id).first()
            if post:
                if success:
                    post.status = "PUBLISHED"
                    post.published_at = datetime.now(timezone.utc)
                    logger.info(f"Content: post {post_id} published successfully")
                else:
                    post.status = "FAILED"
                    post.error_msg = "Publisher returned False"
                    logger.error(f"Content: post {post_id} failed to publish")
                db.commit()

        # Register content hash for duplicate detection
        if success:
            try:
                from backend.research.duplicate_detector import register_post
                with _get_db() as db_dup:
                    register_post(text, post_id, db_dup)
            except Exception:
                pass

        # Post quality logging for self-learning
        if success:
            try:
                from backend.storage import quality_log
                with _get_db() as db_ql:
                    quality_log.log_post(
                        db=db_ql,
                        topic=post.topic if post else "",
                        style=post.style if post else "",
                        post_text=text,
                        quality_score=0.0,  # score not available at publish time
                        was_published=True,
                    )
            except Exception:
                pass

        # Budget tracking
        if success:
            try:
                from backend.storage.database import get_db as _get_db2
                from backend.storage import budget_tracker
                with _get_db2() as db2:
                    budget_tracker.increment("posts_published", db2)
            except Exception:
                pass

        # WebSocket notification
        try:
            from backend.api.websocket import schedule_broadcast
            schedule_broadcast("activity", {
                "action": "POST_PUBLISHED",
                "target": "LinkedIn Feed",
                "result": "SUCCESS" if success else "FAILED",
            })
        except Exception:
            pass

    finally:
        await browser.close()


def _mark_failed(post_id: str, reason: str) -> None:
    try:
        from backend.storage.database import get_db as _get_db
        with _get_db() as db:
            post = db.query(ScheduledPost).filter_by(id=post_id).first()
            if post:
                post.status = "FAILED"
                post.error_msg = reason
                db.commit()
    except Exception as e:
        logger.warning(f"Content: could not mark post {post_id} failed — {e}")
