import asyncio
from pathlib import Path
from types import SimpleNamespace

import outlook_mail_extractor.__main__ as cli_main
from outlook_mail_extractor.contracts.dependency_guard import (
    DEPENDENCY_GUARD_EXIT_CODE,
    DEPENDENCY_GUARD_REASON,
)
from outlook_mail_extractor.models import DependencyGuardError


class _FakeLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)

    def exception(self, message: str) -> None:
        self.messages.append(message)


class _FakeLoggerManager:
    def start_session(self, enable_ui_sink: bool = False) -> Path:
        del enable_ui_sink
        return Path("dummy.log")


class _GuardFailingService:
    def __init__(self, **kwargs) -> None:
        del kwargs

    async def process_config_file(self, **kwargs):
        del kwargs
        raise DependencyGuardError("Detected incompatible httpx for LLM path")


class _UnexpectedFailingService:
    def __init__(self, **kwargs) -> None:
        del kwargs

    async def process_config_file(self, **kwargs):
        del kwargs
        raise RuntimeError("boom")


def _build_runtime(config_file: Path) -> SimpleNamespace:
    return SimpleNamespace(
        paths=SimpleNamespace(
            config_file=config_file,
            llm_config_file=config_file.parent / "llm-config.yaml",
            plugins_dir=config_file.parent / "plugins",
        ),
        logger_manager=_FakeLoggerManager(),
        client_factory=lambda: None,
    )


def test_cli_dependency_guard_maps_to_contract_exit_and_reason(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("jobs: []\n", encoding="utf-8")

    fake_logger = _FakeLogger()
    monkeypatch.setattr(
        cli_main, "get_runtime_context", lambda: _build_runtime(config_file)
    )
    monkeypatch.setattr(cli_main, "get_logger", lambda: fake_logger)
    monkeypatch.setattr(cli_main, "JobExecutionService", _GuardFailingService)
    monkeypatch.setattr(cli_main, "resolve_terminal_title", lambda _path: "Mailslide")
    monkeypatch.setattr(cli_main, "set_terminal_title", lambda _title: None)
    monkeypatch.setattr(
        cli_main.sys,
        "argv",
        ["mailslide", "--config", str(config_file), "--skip-preflight"],
    )

    exit_code = asyncio.run(cli_main.async_main())
    stderr = capsys.readouterr().err

    assert exit_code == DEPENDENCY_GUARD_EXIT_CODE
    assert DEPENDENCY_GUARD_REASON in stderr
    assert "incompatible httpx" in stderr


def test_cli_non_guard_failure_keeps_generic_exit_code(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("jobs: []\n", encoding="utf-8")

    fake_logger = _FakeLogger()
    monkeypatch.setattr(
        cli_main, "get_runtime_context", lambda: _build_runtime(config_file)
    )
    monkeypatch.setattr(cli_main, "get_logger", lambda: fake_logger)
    monkeypatch.setattr(cli_main, "JobExecutionService", _UnexpectedFailingService)
    monkeypatch.setattr(cli_main, "resolve_terminal_title", lambda _path: "Mailslide")
    monkeypatch.setattr(cli_main, "set_terminal_title", lambda _title: None)
    monkeypatch.setattr(
        cli_main.sys,
        "argv",
        ["mailslide", "--config", str(config_file), "--skip-preflight"],
    )

    exit_code = asyncio.run(cli_main.async_main())
    stderr = capsys.readouterr().err

    assert exit_code == 1
    assert DEPENDENCY_GUARD_REASON not in stderr
    assert "boom" in stderr
