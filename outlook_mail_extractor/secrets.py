"""Windows DPAPI helpers for local secret storage."""

from __future__ import annotations

import os
from pathlib import Path


LLM_API_KEY_FILE_NAME = "llm-api-key.bin"
_DPAPI_DESCRIPTION = "mailslide.llm_api_key"


def llm_api_key_secret_path(llm_config_path: Path) -> Path:
    """Resolve API key secret file path next to `llm-config.yaml`."""
    return llm_config_path.with_name(LLM_API_KEY_FILE_NAME)


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is only available on Windows")


def _dpapi_encrypt(raw: bytes) -> bytes:
    _require_windows()
    try:
        import win32crypt  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("pywin32 is required for Windows DPAPI support") from e
    return win32crypt.CryptProtectData(raw, _DPAPI_DESCRIPTION, None, None, None, 0)


def _dpapi_decrypt(raw: bytes) -> bytes:
    _require_windows()
    try:
        import win32crypt  # type: ignore[import-not-found]
    except ImportError as e:
        raise RuntimeError("pywin32 is required for Windows DPAPI support") from e
    _description, decrypted = win32crypt.CryptUnprotectData(raw, None, None, None, 0)
    return decrypted


def store_llm_api_key(api_key: str, secret_path: Path) -> Path:
    """Encrypt and store LLM API key with DPAPI."""
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = _dpapi_encrypt(api_key.encode("utf-8"))
    temp_path = secret_path.with_name(f".{secret_path.name}.tmp")
    temp_path.write_bytes(encrypted)
    temp_path.replace(secret_path)
    return secret_path


def load_llm_api_key(secret_path: Path) -> str:
    """Load and decrypt LLM API key from DPAPI-protected file."""
    encrypted = secret_path.read_bytes()
    decrypted = _dpapi_decrypt(encrypted)
    return decrypted.decode("utf-8")


def clear_llm_api_key(secret_path: Path) -> None:
    """Delete stored LLM API key file when it exists."""
    if secret_path.exists():
        secret_path.unlink()
