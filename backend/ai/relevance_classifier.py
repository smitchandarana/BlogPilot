"""
Relevance classifier — scores a LinkedIn post 0-10 against configured topics.

Usage:
    result = await classify(post_text, author_name, topics, groq_client, prompt_loader)
    # {"score": 7.5, "reason": "Post discusses Power BI dashboards..."}
"""
import json
import re
from typing import Union

from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are a LinkedIn relevance scoring assistant. "
    "Respond only with valid JSON — no markdown, no extra text."
)

# Fallback: extract first JSON object from messy output
_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _parse_score_response(text: str) -> dict:
    """
    Parse {"score": <number>, "reason": "<string>"} from Groq output.
    Returns {"score": 0.0, "reason": "parse_error"} on failure.
    """
    try:
        data = json.loads(text)
        return {
            "score": float(data.get("score", 0)),
            "reason": str(data.get("reason", "")),
        }
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting first JSON-like object
    match = _JSON_RE.search(text)
    if match:
        try:
            data = json.loads(match.group())
            return {
                "score": float(data.get("score", 0)),
                "reason": str(data.get("reason", "")),
            }
        except Exception:
            pass

    logger.warning(f"RelevanceClassifier: could not parse response: {text[:200]}")
    return {"score": 0.0, "reason": "parse_error"}


async def classify(
    post_text: str,
    author_name: str,
    topics: Union[str, list],
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
) -> dict:
    """
    Score post relevance via Groq.

    Args:
        post_text:     Full text of the LinkedIn post.
        author_name:   Display name of the post author.
        topics:        Comma-separated string or list of target topics.
        groq_client:   Configured GroqClient instance.
        prompt_loader: Loaded PromptLoader instance.

    Returns:
        {"score": float (0-10), "reason": str}
    """
    if isinstance(topics, list):
        topics = ", ".join(str(t) for t in topics)

    try:
        prompt = prompt_loader.format(
            "relevance",
            post_text=post_text,
            author_name=author_name,
            topics=topics,
        )
        raw = await groq_client.complete(_SYSTEM, prompt)
        result = _parse_score_response(raw)
        logger.info(
            f"RelevanceClassifier: author='{author_name}' "
            f"score={result['score']} reason='{result['reason'][:60]}'"
        )
        return result
    except GroqError as e:
        logger.error(f"RelevanceClassifier: Groq error — {e}")
        return {"score": 0.0, "reason": "groq_error"}
    except Exception as e:
        logger.error(f"RelevanceClassifier: unexpected error — {e}", exc_info=True)
        return {"score": 0.0, "reason": "error"}
