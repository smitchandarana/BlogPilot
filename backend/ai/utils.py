"""
Shared AI utility functions.

Provides parse_json_safe() used by content_extractor and post_generator
to parse LLM output that may include markdown fences or minor formatting noise.
"""
import json
import re
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def parse_json_safe(raw: str, context: str = "") -> Any | None:
    """
    Parse JSON from LLM output with multiple fallback strategies.

    Strategy:
      1. Direct json.loads
      2. Strip markdown code fences (```json ... ```) then json.loads
      3. Regex extract first {...} or [...] block then json.loads
      4. Return None on all failures

    Args:
        raw:     Raw string from LLM response.
        context: Optional label for log messages (e.g. "angle_generator").

    Returns:
        Parsed dict/list/value, or None if all strategies fail.
    """
    if not raw:
        return None

    text = raw.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Strategy 3: regex extract first JSON object or array
    for pattern in (r'\{.*\}', r'\[.*\]'):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                continue

    label = f" [{context}]" if context else ""
    logger.warning(f"parse_json_safe{label}: all strategies failed — raw length={len(raw)}")
    return None
