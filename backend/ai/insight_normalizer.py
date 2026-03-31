"""
Insight Normalizer — shapes raw ContentInsight into clean, prompt-ready thinking.

Just-in-time normalization before generation. Converts inconsistently phrased extracted
insights into a structured brief with scenario, core_problem, root_cause, insight_statement.

Usage:
    from backend.ai.insight_normalizer import normalize
    brief = await normalize(insight, groq_client, prompt_loader)
    # Returns dict or None if normalization fails / specificity too low
"""
import json

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are a content strategist. "
    "Return ONLY valid JSON. No preamble, no markdown fences, no explanation."
)

_VALID_ANGLES = {"mistake", "contrarian", "inefficiency", "realization"}


async def normalize(insight, groq_client, prompt_loader) -> dict | None:
    """
    Normalize a raw ContentInsight into clean prompt-ready fields.

    Args:
        insight:       ContentInsight ORM row (or dict with same fields).
        groq_client:   Configured GroqClient instance.
        prompt_loader: Loaded PromptLoader instance.

    Returns:
        Dict with keys: scenario, core_problem, root_cause, insight_statement,
        narrative_angle, specificity_score.
        Returns None if Groq fails or specificity_score < 0.5.
    """
    if groq_client is None or prompt_loader is None:
        return None

    def _get(field, default="none"):
        val = getattr(insight, field, None) if not isinstance(insight, dict) else insight.get(field)
        return str(val).strip() if val else default

    try:
        prompt = prompt_loader.format(
            "insight_normalizer",
            scenario=_get("scenario"),
            pain_point=_get("pain_point"),
            key_insight=_get("key_insight"),
            mistake=_get("mistake"),
            false_belief=_get("false_belief"),
            contradiction=_get("contradiction"),
            evidence=_get("evidence"),
            audience_segment=_get("audience_segment"),
            moment_type=_get("moment_type"),
        )
    except Exception as e:
        logger.warning(f"InsightNormalizer: prompt format failed — {e}")
        return None

    try:
        raw = await groq_client.complete(_SYSTEM, prompt, max_tokens=300)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(raw)
    except Exception as e:
        logger.warning(f"InsightNormalizer: Groq/parse failed — {e}")
        return None

    if not isinstance(data, dict):
        return None

    try:
        specificity = float(data.get("specificity_score", 0))
    except (TypeError, ValueError):
        specificity = 0.0

    if specificity < 0.5:
        logger.debug(f"InsightNormalizer: dropped — specificity {specificity:.2f} < 0.5")
        return None

    angle = str(data.get("narrative_angle", "")).lower().strip()
    if angle not in _VALID_ANGLES:
        angle = "mistake"

    return {
        "scenario": str(data.get("scenario", "")).strip(),
        "core_problem": str(data.get("core_problem", "")).strip(),
        "root_cause": str(data.get("root_cause", "")).strip(),
        "insight_statement": str(data.get("insight_statement", "")).strip(),
        "narrative_angle": angle,
        "specificity_score": specificity,
    }
