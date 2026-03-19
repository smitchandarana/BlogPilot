"""
AI client factory — routes tasks to the correct AI provider.

Rule:
  task="background"  → OpenRouter free (extraction, relevance scoring, topic research)
  task="generation"  → Groq (post gen, comment gen, notes, replies)

This is the ONLY place in the codebase that should instantiate AI clients.
All other modules import build_ai_client() from here.

Raises AIClientUnavailableError (NOT HTTPException) — callers decide how to surface it:
  - API routes: convert to HTTP 503
  - Scheduler/pipeline: log warning and skip the job
"""
import json
import os
from typing import Optional

from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_SECRETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets")


class AIClientUnavailableError(Exception):
    """No AI client could be constructed for the requested task."""


# ── Key loading ───────────────────────────────────────────────────────────────

def _load_groq_key() -> Optional[str]:
    """Load Groq API key from env or config/.secrets/groq.json."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    path = os.path.join(_SECRETS_DIR, "groq.json")
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return data.get("api_key", "").strip() or None
        except Exception as e:
            logger.warning(f"client_factory: failed to read groq.json — {e}")
    return None


def _load_openrouter_key() -> Optional[str]:
    """Load OpenRouter API key from env or config/.secrets/openrouter.json."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    path = os.path.join(_SECRETS_DIR, "openrouter.json")
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return data.get("api_key", "").strip() or None
        except Exception as e:
            logger.warning(f"client_factory: failed to read openrouter.json — {e}")
    return None


# ── Factory ───────────────────────────────────────────────────────────────────

def build_ai_client(task: str = "generation"):
    """
    Build and return an AI client appropriate for the given task.

    Args:
        task: "background" for automated batch processes,
              "generation" for on-demand user-facing output.

    Returns:
        OpenRouterClient (background) or GroqClient (generation).
        May return None for background tasks when no key is available
        (callers should skip gracefully).

    Raises:
        AIClientUnavailableError: For generation tasks when Groq key is missing.
    """
    if task == "background":
        return _build_background_client()
    elif task == "generation":
        return _build_generation_client()
    else:
        raise ValueError(f"build_ai_client: unknown task '{task}' — use 'background' or 'generation'")


def _build_background_client():
    """OpenRouter free → Groq fallback → None."""
    or_key = _load_openrouter_key()
    if or_key:
        from backend.ai.openrouter_client import OpenRouterClient
        model = cfg_get("openrouter.model", "openrouter/free")
        max_tokens = int(cfg_get("openrouter.max_tokens", 400))
        temperature = float(cfg_get("openrouter.temperature", 0.3))
        logger.debug(
            f"build_ai_client: background → OpenRouterClient(model={model})"
        )
        return OpenRouterClient(
            api_key=or_key,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # No OpenRouter key — fall back to Groq (will burn Groq TPD)
    groq_key = _load_groq_key()
    if groq_key:
        logger.warning(
            "build_ai_client: no OpenRouter key — background tasks falling back to Groq. "
            "This burns Groq TPD. Add an OpenRouter key in Settings to fix this."
        )
        return _make_groq_client(groq_key)

    # No client available — callers should skip background jobs gracefully
    logger.warning("build_ai_client: no AI key available for background tasks — skipping")
    return None


def _build_generation_client():
    """Groq only — raises if no key."""
    groq_key = _load_groq_key()
    if not groq_key:
        raise AIClientUnavailableError(
            "Groq API key required for post generation. Add it in Settings → AI Config."
        )
    logger.debug("build_ai_client: generation → GroqClient")
    return _make_groq_client(groq_key)


def _make_groq_client(api_key: str):
    from backend.ai.groq_client import GroqClient
    model = cfg_get("ai.model", "llama-3.3-70b-versatile")
    max_tokens = int(cfg_get("ai.max_tokens", 500))
    temperature = float(cfg_get("ai.temperature", 0.7))
    return GroqClient(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
