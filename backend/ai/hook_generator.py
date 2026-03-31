"""
Hook Generator — pre-generates 5 typed hooks before final post generation.

Hooks drive scroll performance. Pre-generating forces specificity and gives
the generation prompt a concrete first sentence to build from.

Usage:
    hooks = await generate_hooks(normalized_brief, audience, groq_client, prompt_loader)
    best = select_best_hook(hooks, hook_intent="MISTAKE")
"""
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are a LinkedIn hook writer. "
    "Return exactly 5 hooks, one per line. No numbering. No explanation. Nothing else."
)

# Map hook_intent values to their position in the generated list (0-indexed)
_HOOK_INTENT_INDEX = {
    "MISTAKE": 0,
    "CONTRARIAN": 1,
    "STORY": 2,
    "QUESTION": 2,    # story/scenario hook works well for question too
    "TREND": 3,       # observation is closest to trend
    "STAT": 3,        # observation with specifics
}


async def generate_hooks(
    normalized_brief: dict,
    audience: str,
    groq_client,
    prompt_loader,
) -> list[str]:
    """
    Generate 5 hook candidates from a normalized insight brief.

    Args:
        normalized_brief: Dict from insight_normalizer.normalize() with keys:
                          scenario, core_problem, insight_statement.
        audience:         Target audience string.
        groq_client:      Configured GroqClient instance.
        prompt_loader:    Loaded PromptLoader instance.

    Returns:
        List of up to 5 hook strings. Empty list on failure.
    """
    if not groq_client or not prompt_loader or not normalized_brief:
        return []

    scenario = normalized_brief.get("scenario", "")
    core_problem = normalized_brief.get("core_problem", "")
    insight_statement = normalized_brief.get("insight_statement", "")

    if not any([scenario, core_problem, insight_statement]):
        return []

    try:
        prompt = prompt_loader.format(
            "hook_generator",
            scenario=scenario or "Not specified",
            core_problem=core_problem or "Not specified",
            insight_statement=insight_statement or "Not specified",
            audience=audience or "Business decision makers",
        )
    except Exception as e:
        logger.warning(f"HookGenerator: prompt format failed — {e}")
        return []

    try:
        raw = await groq_client.complete(_SYSTEM, prompt, max_tokens=200)
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        hooks = [h for h in lines if len(h) > 10][:5]
        logger.info(f"HookGenerator: generated {len(hooks)} hooks")
        return hooks
    except Exception as e:
        logger.warning(f"HookGenerator: Groq failed — {e}")
        return []


def select_best_hook(hooks: list[str], hook_intent: str) -> str:
    """
    Select the hook that best matches the intended hook_intent type.

    Positions 0-4 correspond to: mistake, contrarian, scenario, observation, tension.
    Falls back to hooks[0] if index is out of range.
    """
    if not hooks:
        return ""
    idx = _HOOK_INTENT_INDEX.get(hook_intent.upper(), 0)
    return hooks[idx] if idx < len(hooks) else hooks[0]
