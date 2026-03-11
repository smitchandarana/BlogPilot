"""
Groq API client with retry logic and rate-limit handling.

Usage:
    client = GroqClient(api_key=..., model=..., max_tokens=..., temperature=...)
    output = await client.complete(system_prompt, user_prompt)
"""
import asyncio
import time
from typing import Optional

from groq import AsyncGroq, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GroqError(Exception):
    """Raised when a Groq API call fails unrecoverably."""


class GroqClient:
    """
    Async Groq API wrapper.

    Retries up to 2 times with exponential backoff (2s, 4s).
    On 429 rate-limit, sleeps 60 s before retrying.
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

    async def complete(self, system: str, user: str) -> str:
        """
        Call Groq chat completion. Returns the text of the first choice.

        Retries twice on transient errors (2 s then 4 s delay).
        On 429, waits 60 s before retrying.
        Raises GroqError if all attempts fail.
        """
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
                        max_tokens=self.max_tokens,
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
                logger.warning(f"GroqClient: 429 rate-limit hit — sleeping 60 s (attempt {attempt})")
                last_error = e
                await asyncio.sleep(60)

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
