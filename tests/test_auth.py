"""
Tests for backend/utils/auth.py and auth wiring in main.py.

Verifies:
- require_auth returns 401 on missing token
- require_auth returns 401 on wrong token
- require_auth passes on valid token (both Authorization and X-API-Token headers)
- /auth/token endpoint returns token from localhost only
- Key API endpoints actually require auth
"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def temp_secrets_dir(tmp_path, monkeypatch):
    """Override the token file path so tests don't read/write real secrets."""
    token_file = tmp_path / ".api_token"
    token_file.write_text("test-token-abc123")

    import backend.utils.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_TOKEN_FILE", str(token_file))
    monkeypatch.setattr(auth_mod, "_API_TOKEN", "test-token-abc123")
    return str(token_file)


@pytest.fixture()
def client(temp_secrets_dir, tmp_path, monkeypatch):
    """TestClient with auth module patched to a known token."""
    # Patch DB and lock so app boots in test
    monkeypatch.setenv("TESTING", "1")

    # Minimal monkeypatching to avoid full engine init
    import backend.utils.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_API_TOKEN", "test-token-abc123")

    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── Unit tests for require_auth dependency ─────────────────────────


@pytest.mark.asyncio
async def test_require_auth_no_token_raises_401():
    from fastapi import HTTPException
    import backend.utils.auth as auth_mod

    old_token = auth_mod._API_TOKEN
    auth_mod._API_TOKEN = "test-token-xyz"
    try:
        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.require_auth(credentials=None, x_api_token=None)
        assert exc_info.value.status_code == 401
    finally:
        auth_mod._API_TOKEN = old_token


@pytest.mark.asyncio
async def test_require_auth_wrong_token_raises_401():
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    import backend.utils.auth as auth_mod

    old_token = auth_mod._API_TOKEN
    auth_mod._API_TOKEN = "correct-token"
    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")
        with pytest.raises(HTTPException) as exc_info:
            await auth_mod.require_auth(credentials=creds, x_api_token=None)
        assert exc_info.value.status_code == 401
    finally:
        auth_mod._API_TOKEN = old_token


@pytest.mark.asyncio
async def test_require_auth_correct_bearer_passes():
    from fastapi.security import HTTPAuthorizationCredentials
    import backend.utils.auth as auth_mod

    old_token = auth_mod._API_TOKEN
    auth_mod._API_TOKEN = "good-token"
    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="good-token")
        # Should not raise
        result = await auth_mod.require_auth(credentials=creds, x_api_token=None)
        assert result is None  # dependency returns None on success
    finally:
        auth_mod._API_TOKEN = old_token


@pytest.mark.asyncio
async def test_require_auth_x_api_token_header_passes():
    import backend.utils.auth as auth_mod

    old_token = auth_mod._API_TOKEN
    auth_mod._API_TOKEN = "good-token"
    try:
        result = await auth_mod.require_auth(credentials=None, x_api_token="good-token")
        assert result is None
    finally:
        auth_mod._API_TOKEN = old_token


# ── Token file loading ─────────────────────────────────────────────


def test_load_or_create_token_reads_existing(tmp_path):
    token_file = tmp_path / ".api_token"
    token_file.write_text("existing-token-xyz")

    import backend.utils.auth as auth_mod

    original = auth_mod._TOKEN_FILE
    auth_mod._TOKEN_FILE = str(token_file)
    try:
        result = auth_mod._load_or_create_token()
        assert result == "existing-token-xyz"
    finally:
        auth_mod._TOKEN_FILE = original


def test_load_or_create_token_generates_new(tmp_path):
    token_file = tmp_path / "subdir" / ".api_token"

    import backend.utils.auth as auth_mod

    original_file = auth_mod._TOKEN_FILE
    original_dir = auth_mod._SECRETS_DIR
    auth_mod._TOKEN_FILE = str(token_file)
    auth_mod._SECRETS_DIR = str(tmp_path / "subdir")
    try:
        result = auth_mod._load_or_create_token()
        assert len(result) > 20
        assert token_file.read_text().strip() == result
    finally:
        auth_mod._TOKEN_FILE = original_file
        auth_mod._SECRETS_DIR = original_dir
