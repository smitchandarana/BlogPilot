"""
Post generator — creates an original LinkedIn post on a given topic.

Sprint 10: Enhanced with quality gate scoring before publishing.

Usage:
    result = await generate(topic, style, tone, word_count, groq_client, prompt_loader)
    # result is a dict: {"post": str, "quality_score": float, "approved": bool, ...}
"""
import json

from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.utils.logger import get_logger
from backend.utils.config_loader import get as cfg_get

logger = get_logger(__name__)

_SYSTEM = (
    "You are a LinkedIn content strategist. "
    "Write only the post text — no title, no intro, no explanation."
)

_SYSTEM_SCORER = (
    "You are a post quality evaluator. "
    "Return ONLY valid JSON. No preamble, no markdown fences."
)


async def generate(
    topic: str,
    style: str,
    tone: str,
    word_count: int,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
) -> dict:
    """
    Generate a LinkedIn post with quality scoring.

    Args:
        topic:         Subject of the post.
        style:         Post style (e.g. "Thought Leadership", "Tips List").
        tone:          Tone (e.g. "Professional", "Conversational").
        word_count:    Approximate target length in words.
        groq_client:   Configured GroqClient instance.
        prompt_loader: Loaded PromptLoader instance.

    Returns:
        Dict with keys: post, quality_score, approved, rejection_reason,
        improvement_suggestion
    """
    # Step 1: Generate post (existing logic)
    try:
        prompt = prompt_loader.format(
            "post",
            topic=topic,
            style=style,
            tone=tone,
            word_count=word_count,
        )
        raw = await groq_client.complete(_SYSTEM, prompt)
        post_text = raw.strip()
        logger.info(f"PostGenerator: topic='{topic}' style='{style}' chars={len(post_text)}")
    except GroqError as e:
        logger.error(f"PostGenerator: Groq error — {e}")
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": f"Generation failed: {e}",
            "improvement_suggestion": None,
        }
    except Exception as e:
        logger.error(f"PostGenerator: unexpected error — {e}", exc_info=True)
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": f"Generation failed: {e}",
            "improvement_suggestion": None,
        }

    if not post_text:
        return {
            "post": "",
            "quality_score": 0.0,
            "approved": False,
            "rejection_reason": "Empty post generated",
            "improvement_suggestion": None,
        }

    # Step 2: Score the generated post
    quality_score = 0.0
    rejection_reason = None
    improvement_suggestion = None
    approved = True

    try:
        scorer_prompt = prompt_loader.format(
            "post_scorer",
            post_text=post_text,
            topic=topic,
            style=style,
            target_audience="business decision makers",
        )
        raw_score = await groq_client.complete(_SYSTEM_SCORER, scorer_prompt)
        raw_score = raw_score.strip()
        if raw_score.startswith("```"):
            raw_score = raw_score.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        score_data = json.loads(raw_score)
        quality_score = float(score_data.get("total", 0))
        rejection_reason = score_data.get("rejection_reason")
        improvement_suggestion = score_data.get("improvement_suggestion")

        logger.info(
            f"PostGenerator: quality score={quality_score}/10 "
            f"publish_rec={score_data.get('publish_recommendation', 'N/A')}"
        )

        # Step 3: Quality gate
        min_score = float(cfg_get("quality.min_post_score", 7))
        if quality_score < min_score:
            approved = False
            if not rejection_reason:
                rejection_reason = f"Score {quality_score} below threshold {min_score}"
            logger.info(
                f"PostGenerator: post REJECTED — score {quality_score}: {rejection_reason}"
            )
        else:
            approved = True
            logger.info(f"PostGenerator: post APPROVED — score {quality_score}")

    except Exception as e:
        # If scoring fails, approve by default (don't block on scoring failure)
        logger.warning(f"PostGenerator: scoring failed ({e}), approving by default")
        approved = True
        quality_score = 0.0

    return {
        "post": post_text,
        "quality_score": quality_score,
        "approved": approved,
        "rejection_reason": rejection_reason,
        "improvement_suggestion": improvement_suggestion,
    }
