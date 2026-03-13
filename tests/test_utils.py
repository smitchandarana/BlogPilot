import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.utils.encryption import encrypt, decrypt
import backend.utils.lock_file as lock_module


@pytest.fixture(autouse=True)
def _isolate_lock(tmp_path):
    """Use a temp lock file so tests don't conflict with running engine."""
    original_path = lock_module._LOCK_PATH
    lock_module._LOCK_PATH = str(tmp_path / "test_engine.lock")
    lock_module._lock_fd = None
    yield
    lock_module.release()
    lock_module._LOCK_PATH = original_path


def test_encrypt_decrypt_roundtrip():
    original = "my_secret_api_key_12345"
    encrypted = encrypt(original)
    assert encrypted != original
    assert decrypt(encrypted) == original


def test_encrypt_produces_different_ciphertext():
    plaintext = "hello"
    c1 = encrypt(plaintext)
    c2 = encrypt(plaintext)
    # Fernet uses random IV so ciphertexts should differ
    assert c1 != c2
    assert decrypt(c1) == decrypt(c2) == plaintext


def test_lock_acquire_release():
    assert lock_module.acquire() is True
    assert lock_module.is_locked()
    lock_module.release()


def test_double_acquire_same_process():
    assert lock_module.acquire() is True
    assert lock_module.is_locked()
    lock_module.release()
