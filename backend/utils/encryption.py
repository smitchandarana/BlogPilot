import os
import socket
import base64
import hashlib

from cryptography.fernet import Fernet
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SECRETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config")
_KEY_FILE = os.path.join(_SECRETS_DIR, ".secrets.key")

_SALT = b"linkedin_ai_engine_v1"


def _derive_key() -> bytes:
    hostname = socket.gethostname().encode("utf-8")
    raw = hostname + _SALT
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def _get_or_create_key() -> bytes:
    os.makedirs(_SECRETS_DIR, exist_ok=True)
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return f.read().strip()

    key = _derive_key()
    with open(_KEY_FILE, "wb") as f:
        f.write(key)
    logger.info(f"New encryption key generated and saved to {_KEY_FILE}")
    return key


def _fernet() -> Fernet:
    key = _get_or_create_key()
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    f = _fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    f = _fernet()
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
