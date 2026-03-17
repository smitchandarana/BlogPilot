"""
Groq API client with retry logic and rate-limit handling.

Usage:
    client = GroqClient(api_key=..., model=..., max_tokens=..., temperature=...)
    output = await client.complete(system_prompt, user_prompt)
"""
import asyncio
import re
import time
from typing import Optional

from groq import AsyncGroq, RateLimitError, APIError

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GroqError(Exception):
    """Raised when a Groq API call fails unrecoverably."""


def _parse_rate_limit(error: RateLimitError) -> tuple[bool, float]:
    """
    Parse a 429 RateLimitError.

    Returns (is_daily_limit, retry_after_seconds).
    - is_daily_limit=True means the daily TPD quota is exhausted — no point retrying.
    - retry_after_seconds is parsed from "Please try again in Xm Ys" if present,
      otherwise defaults to 10s for per-minute limits.
    """
    msg = str(error).lower()
    is_daily = "tokens per day" in msg or " tpd" in msg or "per day" in msg

    # Parse "please try again in 2m30.5s" or "try again in 45s"
    retry_after = 10.0
    m = re.search(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", msg)
    if m:
        minutes = int(m.group(1) or 0)
        seconds = float(m.group(2) or 0)
        retry_after = minutes * 60 + seconds + 1.0  # +1s buffer

    return is_daily, retry_after


class GroqClient:
    """
    Async Groq API wrapper.

    Retries up to 2 times with exponential backoff (2s, 4s).
    On 429 per-minute rate-limit, sleeps the retry-after duration (parsed from error).
    On 429 daily TPD limit, raises GroqError immediately — no point retrying.
    Raises GroqError on unrecoverable failure.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama3-70b-8192",
        max_tokens: int = 500,
        temperature: float = 0.7,
    ):
        if not api_key:
            raise GroqError("GROQ_API_KEY is required but not provided.")
        self._api_key = api_key
        self.model = model
        self.max_tokens = int(max_tokens)
        self.temperature = float(temperature)
        self._client = AsyncGroq(api_key=api_key)

    async def complete(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        """
        Call Groq chat completion. Returns the text of the first choice.

        Retries twice on transient errors (2s, 4s backoff).
        On 429 per-minute limit: sleeps parsed retry-after duration then retries.
        On 429 daily TPD limit: raises GroqError immediately.
        Raises GroqError if all attempts fail.
        """
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt < 3:  # initial + 2 retries
            attempt += 1
            t0 = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    self._client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        max_tokens=tokens,
                        temperature=self.temperature,
                    ),
                    timeout=30.0,
                )
                latency = time.monotonic() - t0
                text = response.choices[0].message.content or ""
                logger.info(
                    f"GroqClient: model={self.model} latency={latency:.2f}s "
                    f"input_chars={len(system)+len(user)} output_chars={len(text)}"
                )
                return text.strip()

            except RateLimitError as e:
                is_daily, retry_after = _parse_rate_limit(e)
                if is_daily:
                    raise GroqError(
                        f"Daily Groq token limit (TPD) reached — resets at midnight UTC. "
                        f"Try again later. ({e})"
                    )
                logger.warning(
                    f"GroqClient: 429 rate-limit hit — sleeping {retry_after:.0f}s (attempt {attempt})"
                )
                last_error = e
                await asyncio.sleep(retry_after)

            except asyncio.TimeoutError as e:
                logger.warning(f"GroqClient: request timed out (attempt {attempt})")
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

            except APIError as e:
                logger.warning(f"GroqClient: API error {e.status_code} (attempt {attempt}): {e.message}")
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(f"GroqClient: unexpected error (attempt {attempt}): {e}", exc_info=True)
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

        raise GroqError(f"Groq call failed after {attempt} attempts: {last_error}")
