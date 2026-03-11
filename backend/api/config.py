import os
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
_PROMPT_NAMES = ["relevance", "comment", "post", "note", "reply"]


# ── Topics ────────────────────────────────────────────────────────

@router.get("/topics")
async def get_topics():
    try:
        from backend.utils.config_loader import get as cfg_get
        topics = cfg_get("topics", []) or []
        return topics
    except Exception:
        return []


@router.post("/topics")
async def update_topics(topics: list[str]):
    import yaml
    from backend.utils.config_loader import load_config
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.yaml")
    config_path = os.path.abspath(config_path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data["topics"] = topics
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        load_config()
    except Exception as e:
        logger.error(f"Failed to persist topics: {e}")
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
    import yaml
    from backend.utils.config_loader import load_config
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.yaml")
    config_path = os.path.abspath(config_path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # Deep merge settings into existing config
        for key, val in settings.items():
            if isinstance(val, dict) and isinstance(data.get(key), dict):
                data[key].update(val)
            else:
                data[key] = val
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
        load_config()
    except Exception as e:
        logger.error(f"Failed to persist settings: {e}")
    return settings


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


class PromptUpdate(BaseModel):
    text: str


@router.put("/prompts/{name}")
async def update_prompt(name: str, body: PromptUpdate):
    if name not in _PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
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
