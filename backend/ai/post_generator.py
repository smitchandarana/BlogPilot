"""
Post generator — creates an original LinkedIn post on a given topic.

Usage:
    text = await generate(topic, style, tone, word_count, groq_client, prompt_loader)
"""
from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are a LinkedIn content strategist. "
    "Write only the post text — no title, no intro, no explanation."
)


async def generate(
    topic: str,
    style: str,
    tone: str,
    word_count: int,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
) -> str:
    """
    Generate a LinkedIn post.

    Args:
        topic:         Subject of the post.
        style:         Post style (e.g. "Thought Leadership", "Tips List").
        tone:          Tone (e.g. "Professional", "Conversational").
        word_count:    Approximate target length in words.
        groq_client:   Configured GroqClient instance.
        prompt_loader: Loaded PromptLoader instance.

    Returns:
        Plain-text post string. Falls back to empty string on error.
    """
    try:
        prompt = prompt_loader.format(
            "post",
            topic=topic,
            style=style,
            tone=tone,
            word_count=word_count,
        )
        raw = await groq_client.complete(_SYSTEM, prompt)
        result = raw.strip()
        logger.info(f"PostGenerator: topic='{topic}' style='{style}' chars={len(result)}")
        return result
    except GroqError as e:
        logger.error(f"PostGenerator: Groq error — {e}")
        return ""
    except Exception as e:
        logger.error(f"PostGenerator: unexpected error — {e}", exc_info=True)
        return ""
