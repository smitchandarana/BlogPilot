"""
Note writer — generates a personalized LinkedIn connection request note.

LinkedIn limit: 300 characters. Output is truncated to the last complete
sentence if the model exceeds the limit.

Usage:
    note = await generate(first_name, title, company, shared_context, topics,
                          groq_client, prompt_loader)
"""
import re
from typing import Union

from backend.ai.groq_client import GroqClient, GroqError
from backend.ai.prompt_loader import PromptLoader
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM = (
    "You are writing a LinkedIn connection request note. "
    "Write only the note text — under 300 characters, no explanation."
)

_MAX_CHARS = 300

# Sentence boundary: ., !, ? followed by space or end of string
_SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")


def _truncate_to_limit(text: str, limit: int = _MAX_CHARS) -> str:
    """Truncate to the last complete sentence at or under *limit* chars."""
    if len(text) <= limit:
        return text

    candidate = text[:limit]
    # Find last sentence ending within candidate
    matches = list(_SENTENCE_END_RE.finditer(candidate))
    if matches:
        last_end = matches[-1].end()
        return candidate[:last_end].strip()

    # No sentence boundary — hard-truncate at word boundary
    return candidate.rsplit(" ", 1)[0].strip()


async def generate(
    first_name: str,
    title: str,
    company: str,
    shared_context: str,
    topics: Union[str, list],
    groq_client: GroqClient,
    prompt_loader: PromptLoader,
) -> str:
    """
    Generate a LinkedIn connection request note (≤ 300 chars).

    Returns plain-text note string. Falls back to empty string on error.
    """
    if isinstance(topics, list):
        topics = ", ".join(str(t) for t in topics)

    try:
        prompt = prompt_loader.format(
            "note",
            first_name=first_name,
            title=title,
            company=company,
            shared_context=shared_context,
            topics=topics,
        )
        raw = await groq_client.complete(_SYSTEM, prompt)
        result = _truncate_to_limit(raw.strip())
        logger.info(
            f"NoteWriter: {first_name} @ {company} — {len(result)} chars"
        )
        return result
    except GroqError as e:
        logger.error(f"NoteWriter: Groq error — {e}")
        return ""
    except Exception as e:
        logger.error(f"NoteWriter: unexpected error — {e}", exc_info=True)
        return ""
