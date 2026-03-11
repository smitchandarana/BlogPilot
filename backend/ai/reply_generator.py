"""
Reply generator — continues a LinkedIn comment thread conversation.

Usage:
    text = await generate(original_post, your_comment, reply_to_comment,
                          replier_name, groq_client, prompt_loader)
"""
from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are continuing a LinkedIn comment thread. "
    "Write only the reply text — 1-3 sentences, no intro, no explanation."
)


async def generate(
    original_post: str,
    your_comment: str,
    reply_to_comment: str,
    replier_name: str,
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
) -> str:
    """
    Generate a reply to a comment in a LinkedIn thread.

    Returns plain-text reply string. Falls back to empty string on error.
    """
    try:
        prompt = prompt_loader.format(
            "reply",
            original_post=original_post,
            your_comment=your_comment,
            reply_to_comment=reply_to_comment,
            replier_name=replier_name,
        )
        raw = await groq_client.complete(_SYSTEM, prompt)
        result = raw.strip()
        logger.info(
            f"ReplyGenerator: replier='{replier_name}' reply_chars={len(result)}"
        )
        return result
    except GroqError as e:
        logger.error(f"ReplyGenerator: Groq error — {e}")
        return ""
    except Exception as e:
        logger.error(f"ReplyGenerator: unexpected error — {e}", exc_info=True)
        return ""
