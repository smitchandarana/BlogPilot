import os
import base64
import secrets

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SECRETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config")
_KEY_FILE = os.path.join(_SECRETS_DIR, ".secrets.key")
_SALT_FILE = os.path.join(_SECRETS_DIR, ".secrets.salt")

_PBKDF2_ITERATIONS = 480_000


def _get_or_create_salt() -> bytes:
    """Load salt from file, or generate a cryptographically random 16-byte salt."""
    os.makedirs(_SECRETS_DIR, exist_ok=True)
    if os.path.exists(_SALT_FILE):
        with open(_SALT_FILE, "rb") as f:
            return f.read()

    salt = secrets.token_bytes(16)
    fd = os.open(_SALT_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, salt)
    finally:
        os.close(fd)
    logger.info(f"New random salt generated and saved to {_SALT_FILE}")
    return salt


def _derive_key(salt: bytes) -> bytes:
    """Derive a Fernet-compatible key using PBKDF2-HMAC-SHA256."""
    # Use a machine-local passphrase from the key file, or generate one
    passphrase = _get_or_create_passphrase()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    derived = kdf.derive(passphrase)
    return base64.urlsafe_b64encode(derived)


def _get_or_create_passphrase() -> bytes:
    """Load or generate a random passphrase (stored in key file with 0600 permissions)."""
    os.makedirs(_SECRETS_DIR, exist_ok=True)
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return f.read().strip()

    passphrase = secrets.token_bytes(32)
    fd = os.open(_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, passphrase)
    finally:
        os.close(fd)
    logger.info(f"New encryption passphrase generated and saved to {_KEY_FILE}")
    return passphrase


def _fernet() -> Fernet:
    salt = _get_or_create_salt()
    key = _derive_key(salt)
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    f = _fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    f = _fernet()
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
