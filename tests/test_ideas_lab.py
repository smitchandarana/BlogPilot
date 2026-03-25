"""Tests for Ideas Lab backend: prompt loading + 3 API endpoints."""
import pytest


def test_synthesize_brief_prompt_registered():
    """synthesize_brief prompt must be in _PROMPT_NAMES and loadable."""
    from backend.ai.prompt_loader import PromptLoader, _PROMPT_NAMES
    assert "synthesize_brief" in _PROMPT_NAMES, (
        "synthesize_brief not in _PROMPT_NAMES — add it to prompt_loader.py"
    )
    loader = PromptLoader()
    loader.load_all()
    text = loader.get("synthesize_brief")
    assert text and len(text) > 50
    variables = loader.get_variables("synthesize_brief")
    assert "source_count" in variables
    assert "materials" in variables
