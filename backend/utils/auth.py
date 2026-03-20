"""
API authentication — bearer token, auto-generated on first run.

Token is stored at config/.secrets/.api_token (plaintext — it is a local bearer
token, not a secret that needs encryption).

On first boot the token is printed to the terminal so the user can add it to
the UI. The UI reads it from localStorage (set by the Settings page).
"""
import os
import secrets

from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SECRETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config", ".secrets")
_TOKEN_FILE = os.path.join(_SECRETS_DIR, ".api_token")

_bearer = HTTPBearer(auto_error=False)


def _load_or_create_token() -> str:
    """Load the local API token from disk, or generate and save a new one."""
    os.makedirs(_SECRETS_DIR, exist_ok=True)
    if os.path.isfile(_TOKEN_FILE):
        with open(_TOKEN_FILE, "r") as f:
            token = f.read().strip()
        if token:
            return token
    # Generate a new token
    token = secrets.token_urlsafe(32)
    fd = os.open(_TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token.encode("utf-8"))
    finally:
        os.close(fd)
    logger.info(
        f"\n{'='*60}\n"
        f"  API Token (add to Settings → API Token in the UI):\n"
        f"  {token}\n"
        f"{'='*60}"
    )
    return token


# Module-level token (loaded once at import time)
_API_TOKEN: str = _load_or_create_token()


def get_api_token() -> str:
    """Return the current API token (for the Settings page to display it)."""
    return _API_TOKEN


async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    x_api_token: Optional[str] = Header(None, alias="X-API-Token"),
):
    """
    FastAPI dependency — validates bearer token or X-API-Token header.
    Accepts token via:
      - Authorization: Bearer <token>
      - X-API-Token: <token>
    Raises HTTP 401 if missing or invalid.
    """
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif x_api_token:
        token = x_api_token

    if not token or token != _API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API token. Get your token from Settings → API Token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
