import asyncio
from pathlib import Path
from types import SimpleNamespace

import mailslide.cli_app as cli_app
from mailslide.cli_args import build_parser
from mailslide.cli_exit_map import map_exception_to_exit_code
from outlook_mail_extractor.contracts.dependency_guard import DEPENDENCY_GUARD_EXIT_CODE
from outlook_mail_extractor.models import DependencyGuardError


def test_parser_keeps_existing_flags() -> None:
    parser = build_parser(Path("config/config.yaml"), "mailslide CLI")
    args = parser.parse_args(
        ["--config", "config/config.yaml", "--dry-run", "--no-move"]
    )
    assert isinstance(args.config, Path)
    assert args.dry_run is True
    assert args.no_move is True


def test_parser_uses_default_config_when_not_provided() -> None:
    parser = build_parser(Path("config/config.yaml"), "mailslide CLI")
    args = parser.parse_args([])
    assert args.config == Path("config/config.yaml")


def test_dependency_guard_maps_to_contract_exit_code() -> None:
    code = map_exception_to_exit_code(DependencyGuardError("blocked"))
    assert code == DEPENDENCY_GUARD_EXIT_CODE


def test_run_cli_async_respects_explicit_empty_argv(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("jobs: []\n", encoding="utf-8")

    class _FakeLogger:
        def info(self, _message: str) -> None:
            pass

        def error(self, _message: str) -> None:
            pass

        def exception(self, _message: str) -> None:
            pass

    class _FakeLoggerManager:
        def start_session(self, enable_ui_sink: bool = False) -> Path:
            del enable_ui_sink
            return Path("dummy.log")

    class _FakePreflight:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def run(self, _config):
            return SimpleNamespace(issues=[])

    class _FakeService:
        def __init__(self, **kwargs) -> None:
            del kwargs

        async def process_config_file(self, **kwargs):
            del kwargs
            return {"ok": True}

    runtime = SimpleNamespace(
        paths=SimpleNamespace(
            config_file=config_file,
            llm_config_file=config_file.parent / "llm-config.yaml",
            plugins_dir=config_file.parent / "plugins",
        ),
        logger_manager=_FakeLoggerManager(),
        client_factory=lambda: None,
    )

    monkeypatch.setattr(cli_app, "get_runtime_context", lambda: runtime)
    monkeypatch.setattr(cli_app, "get_logger", lambda: _FakeLogger())
    monkeypatch.setattr(cli_app, "JobExecutionService", _FakeService)
    monkeypatch.setattr(cli_app, "PreflightCheckService", _FakePreflight)
    monkeypatch.setattr(cli_app, "resolve_terminal_title", lambda _path: "Mailslide")
    monkeypatch.setattr(cli_app, "set_terminal_title", lambda _title: None)
    monkeypatch.setattr(cli_app.sys, "argv", ["mailslide", "--definitely-unknown"])

    exit_code = asyncio.run(cli_app.run_cli_async([]))

    assert exit_code == 0
