"""
Credential encryption - Secures API keys and login credentials.

Uses a machine-local secret key stored in ~/.agent-browser/.secret_key
with restrictive file permissions. Provides encrypt/decrypt functions
for sensitive values stored in config files.

This is NOT military-grade encryption but prevents plaintext exposure
of API keys and passwords in config files.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import stat
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Prefix to identify encrypted values in config
ENCRYPTED_PREFIX = "ENC:"

# Key file permissions (owner read/write only)
KEY_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0o600


def _get_key_path(data_dir: Optional[Path] = None) -> Path:
    """Get the path to the secret key file."""
    base = data_dir or Path("~/.agent-browser").expanduser()
    return base / ".secret_key"


def _ensure_key(data_dir: Optional[Path] = None) -> bytes:
    """Get or create the machine-local secret key."""
    key_path = _get_key_path(data_dir)

    if key_path.exists():
        key = key_path.read_bytes()
        if len(key) >= 32:
            return key[:32]

    # Generate new key
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    key_path.write_bytes(key)

    # Set restrictive permissions (Unix only)
    try:
        os.chmod(key_path, KEY_FILE_MODE)
    except (OSError, AttributeError):
        pass  # Windows or permission issue

    logger.info("Generated new encryption key: %s", key_path)
    return key


def _derive_cipher_key(master_key: bytes, salt: bytes = b"agent-browser-v1") -> bytes:
    """Derive a cipher key from the master key using PBKDF2."""
    return hashlib.pbkdf2_hmac("sha256", master_key, salt, iterations=100_000)


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR data with a repeating key."""
    key_len = len(key)
    return bytes(b ^ key[i % key_len] for i, b in enumerate(data))


def encrypt(value: str, data_dir: Optional[Path] = None) -> str:
    """Encrypt a sensitive value. Returns a string prefixed with 'ENC:'.

    Args:
        value: Plaintext value to encrypt
        data_dir: Optional path to the data directory containing .secret_key

    Returns:
        Encrypted string in format 'ENC:<base64_encoded_cipher>'
    """
    if not value or value.startswith(ENCRYPTED_PREFIX):
        return value  # Already encrypted or empty

    master_key = _ensure_key(data_dir)
    cipher_key = _derive_cipher_key(master_key)
    encrypted = _xor_bytes(value.encode("utf-8"), cipher_key)
    encoded = base64.b64encode(encrypted).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{encoded}"


def decrypt(value: str, data_dir: Optional[Path] = None) -> str:
    """Decrypt an encrypted value. Returns plaintext.

    Args:
        value: Encrypted string (prefixed with 'ENC:') or plaintext
        data_dir: Optional path to the data directory containing .secret_key

    Returns:
        Decrypted plaintext string
    """
    if not value or not value.startswith(ENCRYPTED_PREFIX):
        return value  # Not encrypted, return as-is

    encoded = value[len(ENCRYPTED_PREFIX):]
    try:
        master_key = _ensure_key(data_dir)
        cipher_key = _derive_cipher_key(master_key)
        encrypted = base64.b64decode(encoded)
        decrypted = _xor_bytes(encrypted, cipher_key)
        return decrypted.decode("utf-8")
    except Exception as e:
        logger.error("Failed to decrypt value: %s", e)
        return value  # Return raw value on error


def is_encrypted(value: str) -> bool:
    """Check if a value is encrypted."""
    return bool(value) and value.startswith(ENCRYPTED_PREFIX)


def mask_value(value: str, data_dir: Optional[Path] = None) -> str:
    """Mask a sensitive value for display (e.g., 'sk-xxxx...yyyy')."""
    if not value:
        return "(not set)"
    # Decrypt first if encrypted
    plain = decrypt(value, data_dir) if is_encrypted(value) else value
    if len(plain) <= 8:
        return "***"
    return plain[:5] + "..." + plain[-4:]
