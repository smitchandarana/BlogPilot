"""
Research API — topic research, scoring, and context-enriched post generation.

Endpoints:
  POST /research/trigger                → manually trigger research
  GET  /research/topics                 → list researched topics
  GET  /research/topics/{id}            → single topic with snippets
  POST /research/topics/{id}/generate   → generate post from researched topic
  DELETE /research/topics/{id}          → dismiss a researched topic
  GET  /research/status                 → research status info
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get
from backend.storage.database import get_db
from backend.research.topic_researcher import (
    TopicResearcher,
    get_latest_research,
    get_topic_detail,
    get_context_for_generation,
    mark_used,
)
from backend.storage.models import ResearchedTopic

logger = get_logger(__name__)
router = APIRouter()

# Track last research run
_last_research_at: datetime | None = None


class GenerateRequest(BaseModel):
    style: Optional[str] = "Thought Leadership"
    tone: Optional[str] = "Professional"
    word_count: Optional[int] = 150


@router.post("/trigger")
async def trigger_research():
    """Manually trigger topic research for all active topics."""
    global _last_research_at

    topics = cfg_get("topics", [])
    if not topics:
        raise HTTPException(status_code=400, detail="No topics configured in settings.yaml")

    if not cfg_get("research.enabled", True):
        raise HTTPException(status_code=400, detail="Research is disabled in settings")

    # Get Groq client and prompt loader if available
    groq_client = None
    prompt_loader = None
    try:
        from backend.ai.groq_client import GroqClient
        from backend.ai.prompt_loader import PromptLoader
        from backend.utils.encryption import decrypt

        api_key = None
        try:
            import os
            secrets_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "config", ".secrets"
            )
            secrets_path = os.path.normpath(secrets_path)
            if os.path.exists(secrets_path):
                with open(secrets_path, "r") as f:
                    for line in f:
                        if line.startswith("groq_api_key="):
                            encrypted = line.strip().split("=", 1)[1]
                            api_key = decrypt(encrypted)
                            break
        except Exception:
            pass

        if api_key:
            groq_client = GroqClient(
                api_key=api_key,
                model=cfg_get("ai.model", "llama-3.3-70b-versatile"),
                max_tokens=int(cfg_get("ai.max_tokens", 500)),
                temperature=float(cfg_get("ai.temperature", 0.7)),
            )
            prompt_loader = PromptLoader()
            prompt_loader.load_all()
    except Exception as e:
        logger.warning(f"Research: could not init AI — falling back to heuristics: {e}")

    researcher = TopicResearcher(groq_client=groq_client, prompt_loader=prompt_loader)

    with get_db() as db:
        results = await researcher.research_topics(topics, db)

    _last_research_at = datetime.now(timezone.utc)

    # Broadcast WebSocket event
    try:
        from backend.api.websocket import schedule_broadcast
        schedule_broadcast("research_complete", {
            "topics_researched": len(results),
            "top_topic": results[0]["topic"] if results else None,
            "top_score": results[0]["composite_score"] if results else 0,
        })
    except Exception:
        pass

    return {
        "status": "completed",
        "topics_researched": len(results),
        "results": results,
    }


@router.get("/topics")
async def list_researched_topics(limit: int = Query(20, ge=1, le=100)):
    """List researched topics sorted by composite score."""
    with get_db() as db:
        topics = get_latest_research(db, limit=limit)
    return topics


@router.get("/topics/{topic_id}")
async def get_researched_topic(topic_id: str):
    """Get a single researched topic with all its snippets."""
    with get_db() as db:
        detail = get_topic_detail(topic_id, db)
    if not detail:
        raise HTTPException(status_code=404, detail="Researched topic not found")
    return detail


@router.post("/topics/{topic_id}/generate")
async def generate_from_topic(topic_id: str, body: GenerateRequest):
    """Generate a post from a researched topic using enriched context."""
    with get_db() as db:
        detail = get_topic_detail(topic_id, db)
        if not detail:
            raise HTTPException(status_code=404, detail="Researched topic not found")

        context = get_context_for_generation(topic_id, db)

    # Get AI clients
    from backend.ai.groq_client import GroqClient
    from backend.ai.prompt_loader import PromptLoader
    from backend.utils.encryption import decrypt
    from backend.ai import post_generator
    import os

    api_key = None
    try:
        secrets_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets")
        )
        if os.path.exists(secrets_path):
            with open(secrets_path, "r") as f:
                for line in f:
                    if line.startswith("groq_api_key="):
                        encrypted = line.strip().split("=", 1)[1]
                        api_key = decrypt(encrypted)
                        break
    except Exception:
        pass

    if not api_key:
        raise HTTPException(status_code=400, detail="Groq API key not configured")

    groq_client = GroqClient(
        api_key=api_key,
        model=cfg_get("ai.model", "llama-3.3-70b-versatile"),
        max_tokens=int(cfg_get("ai.max_tokens", 500)),
        temperature=float(cfg_get("ai.temperature", 0.7)),
    )
    prompt_loader = PromptLoader()
    prompt_loader.load_all()

    result = await post_generator.generate(
        topic=detail["topic"],
        style=body.style,
        tone=body.tone,
        word_count=body.word_count,
        groq_client=groq_client,
        prompt_loader=prompt_loader,
        context=context,
        suggested_angle=detail.get("suggested_angle", ""),
    )

    # Check for duplicates
    try:
        from backend.research.duplicate_detector import check_duplicate
        with get_db() as db:
            dup = check_duplicate(result["post"], db)
            result["is_duplicate"] = dup["is_duplicate"]
            result["duplicate_similarity"] = dup["similarity"]
            result["duplicate_preview"] = dup["matching_preview"]
    except Exception:
        result["is_duplicate"] = False
        result["duplicate_similarity"] = 0.0
        result["duplicate_preview"] = None

    # Mark topic as used
    with get_db() as db:
        mark_used(topic_id, db)

    return result


@router.delete("/topics/{topic_id}")
async def dismiss_topic(topic_id: str):
    """Dismiss/archive a researched topic."""
    with get_db() as db:
        topic = db.query(ResearchedTopic).filter_by(id=topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        topic.status = "EXPIRED"
        db.commit()
    return {"dismissed": topic_id}


@router.get("/status")
async def research_status():
    """Get research pipeline status."""
    with get_db() as db:
        total = db.query(ResearchedTopic).filter(
            ResearchedTopic.status == "RESEARCHED"
        ).count()

    return {
        "enabled": cfg_get("research.enabled", True),
        "last_run": _last_research_at.isoformat() if _last_research_at else None,
        "scan_interval_hours": cfg_get("research.scan_interval_hours", 6),
        "active_topics": total,
        "sources": {
            "reddit": cfg_get("research.reddit.enabled", True),
            "rss": cfg_get("research.rss.enabled", True),
            "hackernews": cfg_get("research.hackernews.enabled", False),
            "linkedin": True,  # always uses existing feed data
        },
    }
