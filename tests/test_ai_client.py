"""
Tests for the AI layer — groq_client, prompt_loader, and classifiers.

Run:
    pytest tests/test_ai_client.py -v
"""
import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── GroqClient tests ───────────────────────────────────────────────────────

class TestGroqClient:

    def _make_response(self, text: str):
        """Build a mock Groq response object."""
        msg = MagicMock()
        msg.content = text
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Returns stripped text on first attempt."""
        from backend.ai.groq_client import GroqClient

        mock_resp = self._make_response("  Hello world  ")
        with patch("backend.ai.groq_client.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = AsyncMock(return_value=mock_resp)

            client = GroqClient(api_key="test-key")
            result = await client.complete("system", "user")

        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_complete_retries_on_api_error(self):
        """Retries on APIError and succeeds on second attempt."""
        from backend.ai.groq_client import GroqClient
        from groq import APIError

        mock_resp = self._make_response("Success")

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate APIError
                err = APIError.__new__(APIError)
                err.status_code = 500
                err.message = "Internal error"
                raise err
            return mock_resp

        with patch("backend.ai.groq_client.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = side_effect

            with patch("asyncio.sleep", new_callable=AsyncMock):
                client = GroqClient(api_key="test-key")
                result = await client.complete("system", "user")

        assert result == "Success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_complete_raises_after_all_attempts(self):
        """Raises GroqError when all 3 attempts fail."""
        from backend.ai.groq_client import GroqClient, GroqError
        from groq import APIError

        async def always_fail(*args, **kwargs):
            err = APIError.__new__(APIError)
            err.status_code = 500
            err.message = "Always fails"
            raise err

        with patch("backend.ai.groq_client.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = always_fail

            with patch("asyncio.sleep", new_callable=AsyncMock):
                client = GroqClient(api_key="test-key")
                with pytest.raises(GroqError):
                    await client.complete("system", "user")

    @pytest.mark.asyncio
    async def test_rate_limit_retries(self):
        """RateLimitError causes a sleep-then-retry; result is returned on second attempt."""
        from backend.ai.groq_client import GroqClient
        from groq import RateLimitError

        mock_resp = self._make_response("OK after rate limit")
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                err = RateLimitError.__new__(RateLimitError)
                raise err
            return mock_resp

        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("backend.ai.groq_client.AsyncGroq") as MockGroq:
            instance = MockGroq.return_value
            instance.chat.completions.create = side_effect

            with patch("asyncio.sleep", side_effect=mock_sleep):
                client = GroqClient(api_key="test-key")
                result = await client.complete("system", "user")

        assert result == "OK after rate limit"
        assert call_count == 2, "Should have retried once after rate limit"
        assert len(sleep_calls) >= 1, "Should have slept before retry"
        # Sleep duration comes from parsed retry-after or fallback; must be > 0
        assert sleep_calls[0] > 0

    def test_raises_on_empty_key(self):
        """GroqClient raises GroqError immediately if api_key is empty."""
        from backend.ai.groq_client import GroqClient, GroqError
        with pytest.raises(GroqError):
            GroqClient(api_key="")


# ── PromptLoader tests ────────────────────────────────────────────────────

class TestPromptLoader:

    def _make_loader_with_dir(self, prompts: dict):
        """Create a temporary prompts dir and return a PromptLoader for it."""
        import backend.ai.prompt_loader as pl_module

        tmpdir = tempfile.mkdtemp()
        for name, text in prompts.items():
            with open(os.path.join(tmpdir, f"{name}.txt"), "w") as f:
                f.write(text)

        # Patch _PROMPTS_DIR so the loader reads from our temp dir
        original = pl_module._PROMPTS_DIR
        pl_module._PROMPTS_DIR = tmpdir

        from backend.ai.prompt_loader import PromptLoader
        loader = PromptLoader()
        loader.load_all()

        pl_module._PROMPTS_DIR = original  # restore
        return loader, tmpdir

    def test_load_and_get(self):
        from backend.ai.prompt_loader import PromptLoader
        import backend.ai.prompt_loader as pl_module

        tmpdir = tempfile.mkdtemp()
        for name in ["relevance", "comment", "post", "note", "reply"]:
            with open(os.path.join(tmpdir, f"{name}.txt"), "w") as f:
                f.write(f"Hello from {name}")

        original = pl_module._PROMPTS_DIR
        pl_module._PROMPTS_DIR = tmpdir
        try:
            loader = PromptLoader()
            loader.load_all()
            assert loader.get("relevance") == "Hello from relevance"
            assert loader.get("post") == "Hello from post"
        finally:
            pl_module._PROMPTS_DIR = original

    def test_format_fills_variables(self):
        from backend.ai.prompt_loader import PromptLoader
        import backend.ai.prompt_loader as pl_module

        tmpdir = tempfile.mkdtemp()
        template = "Hello {name}, your score is {score}."
        with open(os.path.join(tmpdir, "relevance.txt"), "w") as f:
            f.write(template)
        for name in ["comment", "post", "note", "reply"]:
            with open(os.path.join(tmpdir, f"{name}.txt"), "w") as f:
                f.write("")

        original = pl_module._PROMPTS_DIR
        pl_module._PROMPTS_DIR = tmpdir
        try:
            loader = PromptLoader()
            loader.load_all()
            result = loader.format("relevance", name="Alice", score=9)
            assert result == "Hello Alice, your score is 9."
        finally:
            pl_module._PROMPTS_DIR = original

    def test_format_falls_back_on_missing_variable(self):
        """format() uses manual substitution when format_map fails (unescaped braces)."""
        from backend.ai.prompt_loader import PromptLoader
        import backend.ai.prompt_loader as pl_module

        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "relevance.txt"), "w") as f:
            f.write("Hello {name}, result: {missing_var}")
        for name in ["comment", "post", "note", "reply"]:
            with open(os.path.join(tmpdir, f"{name}.txt"), "w") as f:
                f.write("")

        original = pl_module._PROMPTS_DIR
        pl_module._PROMPTS_DIR = tmpdir
        try:
            loader = PromptLoader()
            loader.load_all()
            # Should not raise — falls back to manual substitution
            result = loader.format("relevance", name="World")
            assert "Hello World" in result
            # Unresolved placeholder left as-is
            assert "{missing_var}" in result
        finally:
            pl_module._PROMPTS_DIR = original

    def test_get_variables(self):
        from backend.ai.prompt_loader import PromptLoader
        import backend.ai.prompt_loader as pl_module

        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "comment.txt"), "w") as f:
            f.write("Post: {post_text} by {author_name} about {topics}")
        for name in ["relevance", "post", "note", "reply"]:
            with open(os.path.join(tmpdir, f"{name}.txt"), "w") as f:
                f.write("")

        original = pl_module._PROMPTS_DIR
        pl_module._PROMPTS_DIR = tmpdir
        try:
            loader = PromptLoader()
            loader.load_all()
            variables = loader.get_variables("comment")
            assert "post_text" in variables
            assert "author_name" in variables
            assert "topics" in variables
        finally:
            pl_module._PROMPTS_DIR = original


# ── RelevanceClassifier tests ─────────────────────────────────────────────

class TestRelevanceClassifier:

    def _make_mock_deps(self, response_text: str):
        from unittest.mock import AsyncMock, MagicMock
        groq_client = MagicMock()
        groq_client.complete = AsyncMock(return_value=response_text)
        prompt_loader = MagicMock()
        prompt_loader.format = MagicMock(return_value="formatted prompt")
        return groq_client, prompt_loader

    @pytest.mark.asyncio
    async def test_classify_valid_json(self):
        from backend.ai.relevance_classifier import classify
        groq_client, prompt_loader = self._make_mock_deps(
            '{"score": 8, "reason": "Directly discusses BI dashboards"}'
        )
        result = await classify("post text", "Author", "Business Intelligence", groq_client, prompt_loader)
        assert result["score"] == 8.0
        assert "BI" in result["reason"] or result["reason"]

    @pytest.mark.asyncio
    async def test_classify_returns_parse_error_on_bad_json(self):
        from backend.ai.relevance_classifier import classify
        groq_client, prompt_loader = self._make_mock_deps("not json at all")
        result = await classify("post text", "Author", "topics", groq_client, prompt_loader)
        assert result["score"] == 0.0
        assert result["reason"] == "parse_error"

    @pytest.mark.asyncio
    async def test_classify_accepts_list_topics(self):
        from backend.ai.relevance_classifier import classify
        groq_client, prompt_loader = self._make_mock_deps('{"score": 7, "reason": "Relevant"}')
        result = await classify("text", "Author", ["BI", "Analytics"], groq_client, prompt_loader)
        assert result["score"] == 7.0


# ── NoteWriter length test ────────────────────────────────────────────────

class TestNoteWriter:

    @pytest.mark.asyncio
    async def test_truncates_to_300_chars(self):
        from backend.ai.note_writer import generate
        long_note = "A" * 400 + ". End."
        groq_client = MagicMock()
        groq_client.complete = AsyncMock(return_value=long_note)
        prompt_loader = MagicMock()
        prompt_loader.format = MagicMock(return_value="formatted")

        result = await generate("John", "CEO", "Acme", "met online", "Analytics", groq_client, prompt_loader)
        assert len(result) <= 300

    @pytest.mark.asyncio
    async def test_short_note_unchanged(self):
        from backend.ai.note_writer import generate
        short = "Hi John, love your work on BI."
        groq_client = MagicMock()
        groq_client.complete = AsyncMock(return_value=short)
        prompt_loader = MagicMock()
        prompt_loader.format = MagicMock(return_value="formatted")

        result = await generate("John", "CEO", "Acme", "met online", "Analytics", groq_client, prompt_loader)
        assert result == short
