"""Helpers for setting terminal window title."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import ctypes
except Exception:  # pragma: no cover
    ctypes = None  # type: ignore[assignment]

import yaml


DEFAULT_TERMINAL_TITLE = "Mailslide"


def set_terminal_title(title: str) -> None:
    if not title:
        return

    try:
        if os.name == "nt":
            _set_windows_console_title(title)
            return
        _set_ansi_terminal_title(title)
    except Exception:
        return


def resolve_terminal_title(config_path: Path | str) -> str:
    default = DEFAULT_TERMINAL_TITLE
    try:
        path = Path(config_path)
        if not path.exists():
            return default

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            return default

        value = loaded.get("terminal_title")
        if not isinstance(value, str):
            return default

        title = value.strip()
        if not title:
            return default

        return title
    except Exception:
        return default


def _set_windows_console_title(title: str) -> None:
    try:
        if ctypes is None:
            raise RuntimeError("ctypes unavailable")
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception:
        _set_ansi_terminal_title(title)


def _set_ansi_terminal_title(title: str) -> None:
    if not getattr(sys.stdout, "isatty", lambda: False)():
        return
    sys.stdout.write(f"\x1b]0;{title}\x07")
    sys.stdout.flush()
