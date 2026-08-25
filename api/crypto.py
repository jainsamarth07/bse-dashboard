"""
AES-256-GCM encryption for broker API keys at rest.

In production, replace the hardcoded key with:
  - AWS KMS / GCP KMS envelope encryption, or
  - A key loaded from a secrets manager (Vault, Doppler, etc.)

The ENCRYPTION_KEY env var must be a 32-byte hex string (64 hex chars).
Generate one with:  python -c "import os; print(os.urandom(32).hex())"
"""

from __future__ import annotations

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_key() -> bytes:
    hex_key = os.getenv("ENCRYPTION_KEY", "0" * 64)  # 32 zero-bytes for dev
    return bytes.fromhex(hex_key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string → base64-encoded ciphertext (nonce prepended)."""
    if not plaintext:
        return ""
    key = _get_key()
    aes = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext."""
    if not ciphertext:
        return ""
    key = _get_key()
    aes = AESGCM(key)
    raw = base64.b64decode(ciphertext)
    nonce, ct = raw[:12], raw[12:]
    return aes.decrypt(nonce, ct, None).decode("utf-8")
