import os
import json as _json
import tempfile
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
_SECRETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets")
_PROMPT_NAMES = [
    "relevance", "comment", "post", "note", "reply",
    "comment_candidate", "comment_scorer", "post_scorer", "post_with_context",
    "topic_scorer", "topic_extractor", "content_extractor", "structured_post",
    "angle_generator", "insight_normalizer", "hook_generator", "post_critic",
    "synthesize_brief",
]


def _write_secret(path: str, data: bytes) -> None:
    """Write *data* to *path* atomically (temp-file + rename) with mode 0o600."""
    dir_ = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=dir_)
    try:
        os.write(fd, data)
        os.close(fd)
        fd = -1
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)  # atomic on POSIX; near-atomic on Windows
    except Exception:
        if fd != -1:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
                from backend.utils.encryption import decrypt
                with open(groq_path, "r") as f:
                    data = _json.load(f)
                raw = data.get("api_key", "")
                try:
                    key = decrypt(raw)
                except Exception:
                    key = raw  # plaintext fallback
                source = "file"
            except Exception:
                pass
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        return {"configured": True, "source": source, "masked_key": masked}
    return {"configured": False, "source": None, "masked_key": None}


@router.get("/api-keys/groq/test")
async def test_groq_key():
    """Test the stored Groq API key by making a minimal real API call."""
    import httpx

    # Resolve key: env var takes priority, then encrypted file
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        groq_path = os.path.join(_SECRETS_DIR, "groq.json")
        if not os.path.isfile(groq_path):
            return {"valid": False, "error": "No API key configured"}
        try:
            from backend.utils.encryption import decrypt
            with open(groq_path, "r") as f:
                data = _json.load(f)
            raw = data.get("api_key", "")
            if not raw:
                return {"valid": False, "error": "No API key configured"}
            try:
                key = decrypt(raw)
            except Exception:
                key = raw  # plaintext fallback
        except Exception:
            return {"valid": False, "error": "No API key configured"}

    if not key:
        return {"valid": False, "error": "No API key configured"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                },
            )
        if resp.status_code == 200:
            return {"valid": True, "model": "llama-3.3-70b-versatile"}
        if resp.status_code == 401:
            return {"valid": False, "error": "Invalid API key"}
        logger.warning(f"Groq key test returned unexpected status {resp.status_code}")
        return {"valid": False, "error": f"Unexpected response: {resp.status_code}"}
    except Exception as e:
        logger.error(f"Groq key test failed with exception: {e}")
        return {"valid": False, "error": f"Connection error: {e}"}


@router.post("/api-keys/groq")
async def save_groq_key(body: ApiKeyUpdate):
    """Save Groq API key encrypted to config/.secrets/groq.json."""
    from backend.utils.encryption import encrypt
    key = body.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    os.makedirs(_SECRETS_DIR, exist_ok=True)
    groq_path = os.path.join(_SECRETS_DIR, "groq.json")
    payload = _json.dumps({"api_key": encrypt(key)}).encode("utf-8")
    _write_secret(groq_path, payload)

    logger.info("Groq API key saved (encrypted) to config/.secrets/groq.json")
    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return {"configured": True, "masked_key": masked}


@router.get("/api-keys/openrouter")
async def get_openrouter_key_status():
    """Check if OpenRouter API key is configured (never returns the actual key)."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    source = "env"
    if not key:
        or_path = os.path.join(_SECRETS_DIR, "openrouter.json")
        if os.path.exists(or_path):
            try:
                from backend.utils.encryption import decrypt
                with open(or_path, "r") as f:
                    data = _json.load(f)
                raw = data.get("api_key", "")
                try:
                    key = decrypt(raw)
                except Exception:
                    key = raw  # plaintext fallback
                source = "file"
            except Exception:
                pass
    if key:
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        return {"configured": True, "source": source, "masked_key": masked}
    return {"configured": False, "source": None, "masked_key": None}


@router.post("/api-keys/openrouter")
async def save_openrouter_key(body: ApiKeyUpdate):
    """Save OpenRouter API key encrypted to config/.secrets/openrouter.json."""
    from backend.utils.encryption import encrypt
    key = body.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    os.makedirs(_SECRETS_DIR, exist_ok=True)
    or_path = os.path.join(_SECRETS_DIR, "openrouter.json")
    payload = _json.dumps({"api_key": encrypt(key)}).encode("utf-8")
    _write_secret(or_path, payload)

    logger.info("OpenRouter API key saved (encrypted) to config/.secrets/openrouter.json")
    masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    return {"configured": True, "masked_key": masked}


# ── LinkedIn Credentials ──────────────────────────────────────────

class LinkedInCredentials(BaseModel):
    email: str
    password: str


@router.post("/credentials/linkedin")
async def save_linkedin_credentials(body: LinkedInCredentials):
    """Save LinkedIn credentials encrypted to config/.secrets/linkedin.json."""
    from backend.utils.encryption import encrypt

    email = body.email.strip()
    password = body.password.strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    os.makedirs(_SECRETS_DIR, exist_ok=True)
    linkedin_path = os.path.join(_SECRETS_DIR, "linkedin.json")
    payload = _json.dumps({"email": encrypt(email), "password": encrypt(password)}).encode("utf-8")
    _write_secret(linkedin_path, payload)

    logger.info("LinkedIn credentials saved (encrypted)")
    return {"saved": True, "email_hint": email[:3] + "***" + email[email.find("@"):] if "@" in email else "***"}


@router.get("/credentials/linkedin")
async def get_linkedin_credentials_status():
    """Check if LinkedIn credentials are configured (returns status only, never decrypts)."""
    linkedin_path = os.path.join(_SECRETS_DIR, "linkedin.json")
    if not os.path.isfile(linkedin_path):
        return {"configured": False}
    try:
        with open(linkedin_path, "r") as f:
            data = _json.load(f)
        # If email key exists and looks like a Fernet token (long encrypted string), it's configured
        has_email = bool(data.get("email", ""))
        has_password = bool(data.get("password", ""))
        return {"configured": has_email and has_password}
    except Exception:
        return {"configured": False}


class LinkedInTestRequest(BaseModel):
    email: str = ""
    password: str = ""


@router.post("/credentials/linkedin/test")
async def test_linkedin_credentials(body: LinkedInTestRequest = None):
    """Test LinkedIn credentials stub. Saves if provided, validates on engine start."""
    from backend.utils.encryption import encrypt

    # If credentials provided in body, save them
    if body and body.email and body.password:
        email = body.email.strip()
        password = body.password.strip()
        os.makedirs(_SECRETS_DIR, exist_ok=True)
        linkedin_path = os.path.join(_SECRETS_DIR, "linkedin.json")
        payload = _json.dumps({"email": encrypt(email), "password": encrypt(password)})
        _write_secret(linkedin_path, payload.encode("utf-8"))
        logger.info("LinkedIn credentials saved via test endpoint (encrypted)")
        return {"success": True, "message": "Credentials saved. They will be validated when the engine starts."}

    # No body provided — check if stored credentials exist
    linkedin_path = os.path.join(_SECRETS_DIR, "linkedin.json")
    if not os.path.isfile(linkedin_path):
        return {"success": False, "error": "No credentials provided"}
    try:
        with open(linkedin_path, "r") as f:
            data = _json.load(f)
        if data.get("email") and data.get("password"):
            return {"success": True, "message": "Credentials saved. They will be validated when the engine starts."}
        return {"success": False, "error": "No credentials provided"}
    except Exception:
        return {"success": False, "error": "No credentials provided"}


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
    """Return topic performance data including is_active/is_paused for UI status chips."""
    from backend.storage.database import get_db
    from backend.storage.models import TopicPerformance
    with get_db() as db:
        rows = db.query(TopicPerformance).all()
        return [
            {
                "topic": r.topic,
                "engagement_rate": r.engagement_rate,
                "avg_score": r.avg_score,
                "posts_engaged": r.posts_engaged,
                "posts_seen": r.posts_seen,
                "is_active": r.is_active,
                "is_paused": r.is_paused,
                "pause_reason": r.pause_reason or "",
            }
            for r in rows
        ]


@router.post("/topics/run-cycle")
async def run_topic_rotation_cycle():
    """Manually trigger a topic rotation cycle immediately."""
    from backend.storage.database import get_db
    from backend.growth.topic_rotator import topic_rotator
    with get_db() as db:
        report = topic_rotator.run_iteration_cycle(db)
    return report


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


# ── Setup Status ──────────────────────────────────────────────────

@router.get("/setup/status")
async def get_setup_status():
    """
    Returns whether the initial setup is complete.
    Used by the frontend to skip the First-Run Wizard on second launch
    even if localStorage has been cleared (e.g. new machine / EXE reinstall).
    """
    # Groq key configured?
    groq_configured = bool(os.environ.get("GROQ_API_KEY", ""))
    if not groq_configured:
        groq_path = os.path.join(_SECRETS_DIR, "groq.json")
        groq_configured = os.path.isfile(groq_path)

    # LinkedIn credentials saved?
    linkedin_configured = False
    linkedin_path = os.path.join(_SECRETS_DIR, "linkedin.json")
    linkedin_configured = os.path.isfile(linkedin_path)

    # Topics configured (non-empty in settings.yaml)?
    topics_configured = False
    try:
        from backend.utils.config_loader import get as cfg_get
        topics = cfg_get("topics", [])
        topics_configured = isinstance(topics, list) and len(topics) > 0
    except Exception:
        pass

    complete = groq_configured  # Groq key is the minimum requirement
    return {
        "complete": complete,
        "groq_configured": groq_configured,
        "linkedin_configured": linkedin_configured,
        "topics_configured": topics_configured,
    }


# ── Settings ──────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings():
    try:
        from backend.utils.config_loader import all_config
        return all_config()
    except Exception:
        return {}


_SETTINGS_ALLOWLIST = {
    "schedule", "daily_budget", "rate_limits", "delays", "modules",
    "feed_engagement", "viral_detection", "workers", "circuit_breaker",
    "quality", "ai", "openrouter", "email_enrichment", "browser", "storage",
    "analytics", "content_studio", "research", "topic_rotation", "learning",
    "topics", "hashtags", "keyword_blacklist", "target_industries",
    "influencer_watchlist", "competitor_watchlist", "content_intelligence",
}

_SETTINGS_DENYLIST = {"engine"}  # engine.enabled etc. are internal-only


@router.put("/settings")
async def update_settings(settings: dict):
    from backend.utils.config_loader import save_config
    rejected = [k for k in settings if k not in _SETTINGS_ALLOWLIST or k in _SETTINGS_DENYLIST]
    if rejected:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(
            status_code=422,
            detail=f"Rejected settings keys (not configurable via API): {rejected}",
        )
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

        # Resolve API key via client_factory (handles decryption + env fallback)
        from backend.ai.client_factory import _load_groq_key
        api_key = _load_groq_key() or ""

        if not api_key:
            return {"output": "[Error: GROQ_API_KEY not configured. Set env var or add config/.secrets/groq.json]"}

        client = GroqClient(
            api_key=api_key,
            model=cfg_get("ai.model", "llama-3.3-70b-versatile"),
            max_tokens=cfg_get("ai.max_tokens", 500),
            temperature=cfg_get("ai.temperature", 0.7),
        )
        loader = PromptLoader()
        loader.load_all()

        # Route post/comment through their full quality-gated pipelines
        if body.prompt_name == "post":
            from backend.ai.post_generator import generate as gen_post
            result = await gen_post(
                topic=body.variables.get("topic", ""),
                style=body.variables.get("style", "Thought Leadership"),
                tone=body.variables.get("tone", "Professional"),
                word_count=int(body.variables.get("word_count", 150)),
                groq_client=client,
                prompt_loader=loader,
                context=body.variables.get("context", ""),
                suggested_angle=body.variables.get("suggested_angle", ""),
            )
            output = result.get("post", "")
            meta = {}
            if result.get("quality_score"):
                meta["quality_score"] = result["quality_score"]
            if not result.get("approved"):
                meta["rejected"] = True
                meta["rejection_reason"] = result.get("rejection_reason", "Below quality threshold")
                if result.get("improvement_suggestion"):
                    meta["improvement_suggestion"] = result["improvement_suggestion"]
            return {"output": output, **meta}

        elif body.prompt_name == "comment":
            from backend.ai.comment_generator import generate as gen_comment
            result = await gen_comment(
                post_text=body.variables.get("post_text", ""),
                author_name=body.variables.get("author_name", "Unknown"),
                topics=body.variables.get("topics", ""),
                tone=body.variables.get("tone", "professional"),
                groq_client=client,
                prompt_loader=loader,
            )
            output = result.get("comment", "")
            meta = {}
            if result.get("quality_score"):
                meta["quality_score"] = result["quality_score"]
            if result.get("rejected"):
                meta["rejected"] = True
                meta["reject_reasons"] = result.get("reject_reasons", [])
                output = "[All candidates rejected: " + ", ".join(result.get("reject_reasons", ["low quality"])) + "]"
            return {"output": output, **meta}

        else:
            # Other prompts (relevance, note, reply): raw call is fine
            formatted = loader.format(body.prompt_name, **body.variables)
            output = await client.complete("You are a helpful assistant.", formatted)
            return {"output": output}
    except Exception as e:
        logger.error(f"Prompt test failed: {e}")
        return {"output": f"[Error: {e}]"}
