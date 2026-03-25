"""Tests for Ideas Lab backend: prompt loading + 3 API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


def _make_client():
    """Build a TestClient. Uses the shared development DB (data/engine.db)."""
    from backend.storage.database import init_db
    init_db()
    from backend.main import app
    from backend.utils.auth import get_api_token
    token = get_api_token()
    return TestClient(app, headers={"X-API-Token": token})


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


# ── Task 3: GET /content/idea-pool ───────────────────────────────────────────


def test_idea_pool_returns_list():
    """GET /content/idea-pool returns a list (may be empty on fresh DB)."""
    client = _make_client()
    resp = client.get("/content/idea-pool")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_idea_pool_source_filter():
    """source param is accepted without 422."""
    client = _make_client()
    for src in ["all", "linkedin", "reddit", "rss", "my_posts"]:
        resp = client.get(f"/content/idea-pool?source={src}")
        assert resp.status_code == 200, f"source={src} returned {resp.status_code}"


def test_idea_pool_item_shape():
    """If any items exist, each has required keys."""
    client = _make_client()
    resp = client.get("/content/idea-pool?limit=5")
    assert resp.status_code == 200
    items = resp.json()
    for item in items:
        for key in ("id", "source_type", "text", "date", "url", "engagement_score"):
            assert key in item, f"Missing key '{key}' in item"


# ── Task 4: POST /content/synthesize-brief ───────────────────────────────────


def test_synthesize_brief_empty_selections():
    """Returns 422 when selections list is empty."""
    client = _make_client()
    resp = client.post("/content/synthesize-brief", json={"selections": []})
    assert resp.status_code == 422


def test_synthesize_brief_missing_groq_key():
    """Returns 503 when no AI key is configured."""
    from unittest.mock import patch
    from backend.ai.client_factory import AIClientUnavailableError

    client = _make_client()
    payload = {
        "selections": [
            {
                "id": "li_abc",
                "source_type": "LINKEDIN",
                "full_text": "Data dashboards are failing businesses silently.",
                "highlights": [
                    {"text": "Data dashboards are failing businesses silently.", "tag": "Hook"}
                ]
            }
        ]
    }
    with patch("backend.api.content.build_ai_client", side_effect=AIClientUnavailableError("no key")):
        resp = client.post("/content/synthesize-brief", json=payload)
    assert resp.status_code == 503


# ── Task 5: POST /content/generate-from-brief ────────────────────────────────


def test_generate_from_brief_empty_brief():
    """Returns 422 when brief is empty string."""
    client = _make_client()
    resp = client.post("/content/generate-from-brief", json={
        "brief": "",
        "topic": "Data Analytics",
        "style": "Thought Leadership",
        "tone": "Professional",
        "word_count": 150,
    })
    assert resp.status_code == 422


def test_generate_from_brief_missing_groq():
    """Returns 503 when no Groq key configured."""
    from unittest.mock import patch
    from backend.ai.client_factory import AIClientUnavailableError

    client = _make_client()
    with patch("backend.api.content.build_ai_client", side_effect=AIClientUnavailableError("no key")):
        resp = client.post("/content/generate-from-brief", json={
            "brief": "Open with a contrarian take on BI tools.",
            "topic": "Data Analytics",
            "style": "Thought Leadership",
            "tone": "Professional",
            "word_count": 150,
        })
    assert resp.status_code == 503
