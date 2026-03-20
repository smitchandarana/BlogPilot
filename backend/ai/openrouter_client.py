"""
OpenRouter AI client — drop-in replacement for GroqClient for background tasks.

Uses the openai SDK with OpenRouter's base URL.
Default model: "openrouter/free" (meta-router that picks the best available free model,
200k context window, zero cost).

Usage:
    client = OpenRouterClient(api_key="sk-or-...")
    text = await client.complete(system_prompt, user_prompt)
"""
import asyncio
import time
from typing import Optional

from openai import AsyncOpenAI, RateLimitError, APIError

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class OpenRouterError(Exception):
    """Raised when an OpenRouter API call fails unrecoverably."""


class OpenRouterClient:
    """
    Async OpenRouter API wrapper with the same .complete() interface as GroqClient.

    Retries up to 3 attempts with 2s/4s/8s backoff.
    60s timeout per request (free tier is slower than Groq).
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "openrouter/free"  # meta-router: picks best available free model

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 400,
        temperature: float = 0.3,
    ):
        if not api_key:
            raise OpenRouterError("OpenRouter API key is required but not provided.")
        self.model = model
        self.max_tokens = int(max_tokens)
        self.temperature = float(temperature)
        self._client = AsyncOpenAI(api_key=api_key, base_url=self.BASE_URL)

    async def complete(self, system: str, user: str, max_tokens: Optional[int] = None) -> str:
        """
        Call OpenRouter chat completion. Returns the text of the first choice.

        Retries 3 times on transient errors (2s, 4s, 8s backoff).
        60s timeout (free tier models are slower).
        Raises OpenRouterError if all attempts fail.
        """
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt < 3:
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
                    timeout=60.0,
                )
                latency = time.monotonic() - t0
                if not response.choices:
                    raise OpenRouterError("Empty response: no choices returned")
                text = response.choices[0].message.content or ""
                logger.info(
                    f"OpenRouterClient: model={self.model} latency={latency:.2f}s "
                    f"input_chars={len(system)+len(user)} output_chars={len(text)}"
                )
                return text.strip()

            except RateLimitError as e:
                logger.warning(
                    f"OpenRouterClient: 429 rate-limit (attempt {attempt}): {e}"
                )
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

            except asyncio.TimeoutError as e:
                logger.warning(f"OpenRouterClient: request timed out after 60s (attempt {attempt})")
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

            except APIError as e:
                logger.warning(
                    f"OpenRouterClient: API error {getattr(e, 'status_code', '?')} "
                    f"(attempt {attempt}): {e}"
                )
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.error(
                    f"OpenRouterClient: unexpected error (attempt {attempt}): {e}",
                    exc_info=True,
                )
                last_error = e
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

        raise OpenRouterError(f"OpenRouter call failed after {attempt} attempts: {last_error}")
