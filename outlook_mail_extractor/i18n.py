"""Lightweight i18n helpers backed by gettext with YAML fallback."""

from __future__ import annotations

import ctypes
from collections.abc import Mapping
from pathlib import Path
from string import Formatter
import sys

import gettext
import yaml

DEFAULT_LANGUAGE = "en-US"
SUPPORTED_LANGUAGES = {"zh-TW", "en-US"}

_LANGUAGE = DEFAULT_LANGUAGE
_TRANSLATION: gettext.NullTranslations = gettext.NullTranslations()
_FALLBACK_CACHE: dict[str, dict[str, str]] = {}


class _SafeFormatDict(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _normalize_language(language: str | None) -> str:
    if not language:
        return DEFAULT_LANGUAGE

    normalized = str(language).strip().replace("_", "-")
    if not normalized:
        return DEFAULT_LANGUAGE

    if normalized.lower() in {"zh", "zh-tw", "zh-hant"}:
        return "zh-TW"
    if normalized.lower() in {"en", "en-us", "en-gb"}:
        return "en-US"

    if normalized in SUPPORTED_LANGUAGES:
        return normalized

    return DEFAULT_LANGUAGE


def _to_babel_language(language: str) -> str:
    return language.replace("-", "_")


def detect_system_language() -> str:
    """Detect system UI language and normalize to supported language."""
    if sys.platform != "win32":
        return DEFAULT_LANGUAGE

    try:
        locale_name_max_length = 85
        buffer = ctypes.create_unicode_buffer(locale_name_max_length)
        result = ctypes.windll.kernel32.GetUserDefaultLocaleName(
            buffer, locale_name_max_length
        )
        if result > 0 and buffer.value:
            return _normalize_language(buffer.value)
    except Exception:
        pass

    return DEFAULT_LANGUAGE


def _locales_dir() -> Path:
    return Path(__file__).resolve().parent / "locales"


def _gettext_locales_dir() -> Path:
    return _locales_dir() / "gettext"


def _load_yaml_translations(language: str) -> dict[str, str]:
    cached = _FALLBACK_CACHE.get(language)
    if cached is not None:
        return cached

    locale_file = _locales_dir() / f"{language}.yaml"
    if not locale_file.exists():
        _FALLBACK_CACHE[language] = {}
        return {}

    with open(locale_file, encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    if not isinstance(payload, dict):
        _FALLBACK_CACHE[language] = {}
        return {}

    flattened = {str(key): str(value) for key, value in payload.items()}
    _FALLBACK_CACHE[language] = flattened
    return flattened


def _safe_format(message: str, kwargs: Mapping[str, object]) -> str:
    if not kwargs:
        return message

    formatter = Formatter()
    try:
        return formatter.vformat(message, (), _SafeFormatDict(kwargs))
    except Exception:
        return message


def set_language(language: str | None) -> str:
    """Set process-level language and load gettext catalogs when available."""
    global _LANGUAGE
    global _TRANSLATION

    resolved = _normalize_language(language)
    _LANGUAGE = resolved
    _TRANSLATION = gettext.translation(
        domain="messages",
        localedir=str(_gettext_locales_dir()),
        languages=[_to_babel_language(resolved)],
        fallback=True,
    )
    return resolved


def get_language() -> str:
    return _LANGUAGE


def resolve_language(config_path: Path, explicit_language: str | None = None) -> str:
    """Resolve language from CLI override or config file."""
    if explicit_language:
        return _normalize_language(explicit_language)

    if not config_path.exists():
        return detect_system_language()

    try:
        with open(config_path, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
    except Exception:
        return detect_system_language()

    if not isinstance(payload, dict):
        return detect_system_language()

    if "ui_language" in payload:
        return _normalize_language(payload.get("ui_language"))

    return detect_system_language()


def t(key: str, **kwargs: object) -> str:
    """Translate by key with gettext first, then YAML fallback."""
    translated = _TRANSLATION.gettext(key)
    if translated == key:
        lang_map = _load_yaml_translations(_LANGUAGE)
        translated = lang_map.get(key, key)
        if translated == key and _LANGUAGE != DEFAULT_LANGUAGE:
            translated = _load_yaml_translations(DEFAULT_LANGUAGE).get(key, key)
    return _safe_format(translated, kwargs)


set_language(DEFAULT_LANGUAGE)
