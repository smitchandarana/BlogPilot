import os
import json as _json
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
_SECRETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets")
_PROMPT_NAMES = ["relevance", "comment", "post", "note", "reply"]


# ── API Keys ─────────────────────────────────────────────────────

class ApiKeyUpdate(BaseModel):
    api_key: str


@router.get("/api-keys/groq")
async def get_groq_key_status():
    """Check if Groq API key is configured (never returns the actual key)."""
    key = os.environ.get("GROQ_API_KEY", "")
    source = "env"
    if not key:
        groq_path = os.path.join(_SECRETS_DIR, "groq.json")
        if os.path.exists(groq_path):
            try:
                with open(groq_path, "r") as f:
                    data = _json.load(f)
                key = data.get("api_key", "")
                source = "file"
            except Exception:
                pass
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        return {"configured": True, "source": source, "masked_key": masked}
    return {"configured": False, "source": None, "masked_key": None}


@router.post("/api-keys/groq")
async def save_groq_key(body: ApiKeyUpdate):
    """Save Groq API key to config/.secrets/groq.json."""
    key = body.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    os.makedirs(_SECRETS_DIR, exist_ok=True)
    groq_path = os.path.join(_SECRETS_DIR, "groq.json")
    fd = os.open(groq_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, _json.dumps({"api_key": key}).encode("utf-8"))
    finally:
        os.close(fd)

    logger.info("Groq API key saved to config/.secrets/groq.json")
    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return {"configured": True, "masked_key": masked}


# ── Topics ────────────────────────────────────────────────────────

@router.get("/topics")
async def get_topics():
    try:
        from backend.utils.config_loader import get as cfg_get
        topics = cfg_get("topics", []) or []
        return topics
    except Exception:
        return []


@router.get("/topics/all")
async def get_all_topics():
    """Return all topics with their active/paused/available status."""
    from backend.storage.database import get_db
    from backend.growth.topic_rotator import topic_rotator
    with get_db() as db:
        return topic_rotator.get_all_topics(db)


@router.get("/topics/performance")
async def get_topic_performance():
    """Return topic performance data."""
    from backend.storage.database import get_db
    from backend.growth.topic_rotator import topic_rotator
    with get_db() as db:
        data = topic_rotator.get_all_topics(db)
        return data.get("active", [])


@router.post("/topics/{name}/activate")
async def activate_topic(name: str):
    """Activate a paused topic."""
    from backend.storage.database import get_db
    from backend.growth.topic_rotator import topic_rotator
    with get_db() as db:
        result = topic_rotator.activate_topic(name, db)
        if not result:
            raise HTTPException(status_code=404, detail=f"Topic '{name}' not found or already active")
        return {"status": "activated", "topic": name}


@router.post("/topics/{name}/deactivate")
async def deactivate_topic(name: str):
    """Deactivate an active topic."""
    from backend.storage.database import get_db
    from backend.growth.topic_rotator import topic_rotator
    with get_db() as db:
        result = topic_rotator.deactivate_topic(name, db)
        if not result:
            raise HTTPException(status_code=404, detail=f"Topic '{name}' not found or already paused")
        return {"status": "deactivated", "topic": name}


@router.get("/topics/{name}/hashtags")
async def get_hashtag_suggestions(name: str):
    """Get hashtag suggestions for a topic."""
    from backend.growth.topic_rotator import topic_rotator
    return topic_rotator.get_hashtag_suggestions(name)


@router.post("/topics")
async def update_topics(topics: list[str]):
    from backend.utils.config_loader import save_config
    save_config({"topics": topics})
    return topics


# ── Settings ──────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    try:
        from backend.utils.config_loader import all_config
        return all_config()
    except Exception:
        return {}


@router.put("/settings")
async def update_settings(settings: dict):
    from backend.utils.config_loader import save_config
    updated = save_config(settings)
    return updated


# ── Prompts ───────────────────────────────────────────────────────

@router.get("/prompts")
async def get_prompts():
    result = {}
    for name in _PROMPT_NAMES:
        path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
        try:
            with open(path, "r", encoding="utf-8") as f:
                result[name] = f.read()
        except FileNotFoundError:
            result[name] = ""
    return result


@router.get("/prompts/{name}")
async def get_prompt(name: str):
    if name not in _PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"name": name, "text": f.read()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Prompt file not found: {name}.txt")


_MAX_PROMPT_SIZE = 50_000  # 50KB max prompt size


class PromptUpdate(BaseModel):
    text: str


@router.put("/prompts/{name}")
async def update_prompt(name: str, body: PromptUpdate):
    if name not in _PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    if len(body.text) > _MAX_PROMPT_SIZE:
        raise HTTPException(status_code=413, detail=f"Prompt too large (max {_MAX_PROMPT_SIZE} chars)")
    path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body.text)
    logger.info(f"Prompt '{name}' updated")
    return {"name": name, "text": body.text}


@router.get("/prompts/{name}/default")
async def reset_prompt_to_default(name: str):
    if name not in _PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    default_path = os.path.join(_PROMPTS_DIR, f"{name}.txt.default")
    live_path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
    if not os.path.exists(default_path):
        raise HTTPException(status_code=404, detail=f"No default found for prompt '{name}'")
    with open(default_path, "r", encoding="utf-8") as f:
        text = f.read()
    with open(live_path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"name": name, "text": text}


class PromptTestRequest(BaseModel):
    prompt_name: str
    variables: dict


@router.post("/prompts/test")
async def test_prompt(body: PromptTestRequest):
    try:
        import json as _json
        from backend.ai.groq_client import GroqClient
        from backend.ai.prompt_loader import PromptLoader
        from backend.utils.config_loader import get as cfg_get

        # Resolve API key: env var → config/.secrets/groq.json
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            groq_secrets = os.path.join(
                os.path.dirname(__file__), "..", "..", "config", ".secrets", "groq.json"
            )
            if os.path.exists(groq_secrets):
                try:
                    with open(groq_secrets, "r") as f:
                        data = _json.load(f)
                    api_key = data.get("api_key", "")
                except Exception as read_err:
                    logger.warning(f"Could not read groq.json: {read_err}")

        if not api_key:
            return {"output": "[Error: GROQ_API_KEY not configured. Set env var or add config/.secrets/groq.json]"}

        client = GroqClient(
            api_key=api_key,
            model=cfg_get("ai.model", "llama3-70b-8192"),
            max_tokens=cfg_get("ai.max_tokens", 500),
            temperature=cfg_get("ai.temperature", 0.7),
        )
        loader = PromptLoader()
        loader.load_all()
        formatted = loader.format(body.prompt_name, **body.variables)
        output = await client.complete("You are a helpful assistant.", formatted)
        return {"output": output}
    except Exception as e:
        logger.error(f"Prompt test failed: {e}")
        return {"output": f"[Error: {e}]"}
