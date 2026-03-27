import types
from pathlib import Path

from outlook_mail_extractor import terminal_title


def test_set_terminal_title_uses_windows_api(monkeypatch) -> None:
    calls: list[str] = []

    class _Kernel32:
        @staticmethod
        def SetConsoleTitleW(value: str) -> None:
            calls.append(value)

    monkeypatch.setattr(terminal_title.os, "name", "nt")
    monkeypatch.setattr(
        terminal_title,
        "ctypes",
        types.SimpleNamespace(windll=types.SimpleNamespace(kernel32=_Kernel32())),
    )

    terminal_title.set_terminal_title("Mailslide")

    assert calls == ["Mailslide"]


def test_set_terminal_title_uses_ansi_for_tty(monkeypatch) -> None:
    class _Stdout:
        def __init__(self) -> None:
            self.buffer = ""

        def isatty(self) -> bool:
            return True

        def write(self, text: str) -> None:
            self.buffer += text

        def flush(self) -> None:
            return

    fake_stdout = _Stdout()
    monkeypatch.setattr(terminal_title.os, "name", "posix")
    monkeypatch.setattr(terminal_title.sys, "stdout", fake_stdout)

    terminal_title.set_terminal_title("Mailslide")

    assert fake_stdout.buffer == "\x1b]0;Mailslide\x07"


def test_resolve_terminal_title_returns_configured_value(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("terminal_title: Team Inbox\n", encoding="utf-8")

    assert terminal_title.resolve_terminal_title(config_path) == "Team Inbox"


def test_resolve_terminal_title_falls_back_for_invalid_value(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("terminal_title: 123\n", encoding="utf-8")

    assert (
        terminal_title.resolve_terminal_title(config_path)
        == terminal_title.DEFAULT_TERMINAL_TITLE
    )
