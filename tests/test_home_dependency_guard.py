import asyncio
from pathlib import Path
from types import SimpleNamespace

import outlook_mail_extractor.screens.home as home_module
from outlook_mail_extractor.contracts.dependency_guard import (
    DEPENDENCY_GUARD_REASON,
    DEPENDENCY_GUARD_TERMINAL_STATUS,
)
from outlook_mail_extractor.models import DependencyGuardError
from outlook_mail_extractor.screens.home import HomeScreen


class _FakeLoggerManager:
    def __init__(self) -> None:
        self._sink = None

    def set_ui_sink(self, callback):
        self._sink = callback

    def start_session(self, enable_ui_sink: bool = False) -> Path:
        del enable_ui_sink
        return Path("dummy.log")

    def get_current_log_path(self) -> Path | None:
        return Path("dummy.log")


class _GuardFailingService:
    def __init__(self, **kwargs) -> None:
        del kwargs

    async def process_config_file(self, *args, **kwargs):
        del args
        del kwargs
        raise DependencyGuardError("Detected incompatible httpx for LLM path")


class _TestableHomeScreen(HomeScreen):
    def __init__(self, runtime_context) -> None:
        super().__init__(runtime_context=runtime_context)
        self.log_lines: list[str] = []
        self.running_state: bool | None = None

    def call_later(self, callback, *args, **kwargs):
        del kwargs
        callback(*args)

    def _update_log(self, text: str) -> None:
        self.log_lines.append(text)

    def _set_job_running_state(self, is_running: bool) -> None:
        self.running_state = is_running


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


def test_home_execute_jobs_dependency_guard_uses_terminal_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("jobs: []\n", encoding="utf-8")

    monkeypatch.setattr(home_module, "JobExecutionService", _GuardFailingService)
    screen = _TestableHomeScreen(runtime_context=_build_runtime(config_file))

    asyncio.run(screen._execute_jobs())

    assert screen._job_terminal_status == DEPENDENCY_GUARD_TERMINAL_STATUS
    assert screen.running_state is False
    assert screen.log_lines
    last_line = screen.log_lines[-1]
    assert DEPENDENCY_GUARD_TERMINAL_STATUS in last_line
    assert DEPENDENCY_GUARD_REASON in last_line
    assert "Traceback" not in last_line
