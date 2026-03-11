"""
Comment generator — produces a genuine LinkedIn comment for a given post.

Usage:
    text = await generate(post_text, author_name, topics, tone, groq_client, prompt_loader)
"""
from typing import Union

from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are a professional LinkedIn commenter. "
    "Write only the comment text — no intro, no quotes, no explanation."
)


def _clean(text: str) -> str:
    """Strip surrounding quotes and whitespace from model output."""
    text = text.strip()
    if len(text) >= 2 and text[0] in ('"', "'") and text[-1] == text[0]:
        text = text[1:-1].strip()
    return text


async def generate(
    post_text: str,
    author_name: str,
    topics: Union[str, list],
    tone: str,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
) -> str:
    """
    Generate a LinkedIn comment for *post_text*.

    Args:
        post_text:     Full text of the LinkedIn post.
        author_name:   Display name of the post author.
        topics:        Comma-separated string or list of target topics.
        tone:          "professional" | "conversational" | "bold"
        groq_client:   Configured GroqClient instance.
        prompt_loader: Loaded PromptLoader instance.

    Returns:
        Plain-text comment string. Falls back to empty string on error.
    """
    if isinstance(topics, list):
        topics = ", ".join(str(t) for t in topics)

    try:
        prompt = prompt_loader.format(
            "comment",
            post_text=post_text,
            author_name=author_name,
            topics=topics,
            tone=tone,
        )
        raw = await groq_client.complete(_SYSTEM, prompt)
        result = _clean(raw)
        logger.info(
            f"CommentGenerator: author='{author_name}' "
            f"comment_chars={len(result)}"
        )
        return result
    except GroqError as e:
        logger.error(f"CommentGenerator: Groq error — {e}")
        return ""
    except Exception as e:
        logger.error(f"CommentGenerator: unexpected error — {e}", exc_info=True)
        return ""
