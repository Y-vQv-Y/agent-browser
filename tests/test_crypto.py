"""Tests for credential encryption."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from agent_browser.crypto import (
    encrypt,
    decrypt,
    is_encrypted,
    mask_value,
    ENCRYPTED_PREFIX,
    _ensure_key,
    _get_key_path,
)


class TestEncryption:
    def test_encrypt_returns_prefixed(self, tmp_path):
        result = encrypt("my-secret-key", tmp_path)
        assert result.startswith(ENCRYPTED_PREFIX)

    def test_decrypt_roundtrip(self, tmp_path):
        original = "sk-1234567890abcdef"
        encrypted = encrypt(original, tmp_path)
        decrypted = decrypt(encrypted, tmp_path)
        assert decrypted == original

    def test_encrypt_empty_string(self, tmp_path):
        assert encrypt("", tmp_path) == ""

    def test_decrypt_empty_string(self, tmp_path):
        assert decrypt("", tmp_path) == ""

    def test_encrypt_already_encrypted(self, tmp_path):
        encrypted = encrypt("test-value", tmp_path)
        double_encrypted = encrypt(encrypted, tmp_path)
        assert double_encrypted == encrypted  # Should not re-encrypt

    def test_decrypt_plaintext(self, tmp_path):
        """Decrypting a non-encrypted string should return it as-is."""
        assert decrypt("plain-text-key", tmp_path) == "plain-text-key"

    def test_is_encrypted(self, tmp_path):
        encrypted = encrypt("test", tmp_path)
        assert is_encrypted(encrypted) is True
        assert is_encrypted("plain-text") is False
        assert is_encrypted("") is False

    def test_different_data_dirs_different_keys(self, tmp_path):
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        dir2 = tmp_path / "dir2"
        dir2.mkdir()

        enc1 = encrypt("same-secret", dir1)
        enc2 = encrypt("same-secret", dir2)
        # Different keys should produce different ciphertexts
        assert enc1 != enc2

    def test_key_file_created(self, tmp_path):
        _ensure_key(tmp_path)
        key_path = _get_key_path(tmp_path)
        assert key_path.exists()
        assert len(key_path.read_bytes()) >= 32

    def test_key_file_reused(self, tmp_path):
        key1 = _ensure_key(tmp_path)
        key2 = _ensure_key(tmp_path)
        assert key1 == key2

    def test_long_value(self, tmp_path):
        long_val = "x" * 10000
        encrypted = encrypt(long_val, tmp_path)
        decrypted = decrypt(encrypted, tmp_path)
        assert decrypted == long_val

    def test_unicode_value(self, tmp_path):
        unicode_val = "密码123🔑"
        encrypted = encrypt(unicode_val, tmp_path)
        decrypted = decrypt(encrypted, tmp_path)
        assert decrypted == unicode_val


class TestMaskValue:
    def test_mask_normal(self):
        assert mask_value("sk-1234567890abcdef") == "sk-12...cdef"

    def test_mask_short(self):
        assert mask_value("short") == "***"

    def test_mask_empty(self):
        assert mask_value("") == "(not set)"

    def test_mask_encrypted(self, tmp_path):
        encrypted = encrypt("sk-1234567890abcdef", tmp_path)
        masked = mask_value(encrypted, tmp_path)
        assert "sk-12" in masked
        assert "cdef" in masked
