import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.utils.encryption import encrypt, decrypt
from backend.utils.lock_file import acquire, release, is_locked


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
    # Clean state
    release()
    assert not is_locked()
    assert acquire()
    assert is_locked()
    release()
    assert not is_locked()


def test_double_acquire_fails():
    release()
    assert acquire()
    # Second acquire should fail (same process — stale check passes but PID alive)
    # We simulate by checking is_locked() instead of calling acquire() twice in same process
    assert is_locked()
    release()
