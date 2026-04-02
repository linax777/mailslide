from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths
from outlook_mail_extractor.screens.home import HomeScreen


class _FakeLoggerManager:
    def set_ui_sink(self, callback: Any) -> None:
        del callback

    def start_session(self, enable_ui_sink: bool = False) -> Path:
        del enable_ui_sink
        return Path("dummy.log")

    def get_current_log_path(self) -> Path | None:
        return Path("dummy.log")

    def get_display_level(self) -> str:
        return "INFO"

    def set_display_level(self, level: str) -> None:
        del level


class _FakeTable:
    def __init__(self) -> None:
        self.columns: list[str] = []
        self.rows: list[tuple[str, ...]] = []

    def clear(self, columns: bool = False) -> None:
        if columns:
            self.columns = []
            self.rows = []

    def add_columns(self, *columns: str) -> None:
        self.columns.extend(columns)

    def add_row(self, *values: str) -> None:
        self.rows.append(tuple(values))


class _FakeStatic:
    def __init__(self) -> None:
        self.text = ""

    def update(self, text: str) -> None:
        self.text = text


class _FakeButton:
    def __init__(self) -> None:
        self.disabled = False
        self.variant = "default"


class _FakeApp:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str]] = []

    def notify(self, message: object, severity: str = "information") -> None:
        self.notifications.append((str(message), severity))


def _runtime(tmp_path: Path) -> RuntimeContext:
    config_dir = tmp_path / "config"
    paths = RuntimePaths(
        project_root=tmp_path,
        config_dir=config_dir,
        config_file=config_dir / "config.yaml",
        llm_config_file=config_dir / "llm-config.yaml",
        plugins_dir=config_dir / "plugins",
        logging_config_file=config_dir / "logging.yaml",
        logs_dir=tmp_path / "logs",
        readme_file=tmp_path / "README.md",
    )
    return RuntimeContext(
        paths=paths,
        logger_manager=_FakeLoggerManager(),
        client_factory=lambda: None,
    )


class _TestableHomeScreen(HomeScreen):
    def __init__(self, runtime_context: RuntimeContext) -> None:
        super().__init__(runtime_context=runtime_context)
        self.refresh_reasons: list[str] = []
        self.running_states: list[bool] = []
        self.home_active = True
        self.refresh_result = True

    def _refresh_jobs_area(self, reason: str) -> bool:
        self.refresh_reasons.append(reason)
        return self.refresh_result

    def _apply_running_state_to_controls(self, is_running: bool) -> None:
        self.running_states.append(is_running)

    def _is_home_tab_active(self) -> bool:
        return self.home_active


def test_home_auto_refresh_on_entry_triggers_reload_when_idle(tmp_path: Path) -> None:
    screen = _TestableHomeScreen(runtime_context=_runtime(tmp_path))

    screen.request_auto_refresh_on_entry()

    assert screen.refresh_reasons == ["auto"]
    assert screen._pending_auto_refresh is False


def test_home_auto_refresh_on_entry_defers_and_coalesces_when_running(
    tmp_path: Path,
) -> None:
    screen = _TestableHomeScreen(runtime_context=_runtime(tmp_path))
    screen._job_worker = cast(Any, SimpleNamespace(is_running=True))

    screen.request_auto_refresh_on_entry()
    screen.request_auto_refresh_on_entry()

    assert screen.refresh_reasons == []
    assert screen._pending_auto_refresh is True


def test_home_deferred_auto_refresh_drains_once_when_returning_idle_on_home_tab(
    tmp_path: Path,
) -> None:
    screen = _TestableHomeScreen(runtime_context=_runtime(tmp_path))
    screen._pending_auto_refresh = True
    screen.home_active = True

    screen._set_job_running_state(False)

    assert screen.refresh_reasons == ["auto"]
    assert screen._pending_auto_refresh is False


def test_home_deferred_auto_refresh_waits_for_next_home_entry_when_inactive(
    tmp_path: Path,
) -> None:
    screen = _TestableHomeScreen(runtime_context=_runtime(tmp_path))
    screen._pending_auto_refresh = True
    screen.home_active = False

    screen._set_job_running_state(False)

    assert screen.refresh_reasons == []
    assert screen._pending_auto_refresh is True

    screen.home_active = True
    screen.request_auto_refresh_on_entry()

    assert screen.refresh_reasons == ["auto"]
    assert screen._pending_auto_refresh is False


def test_home_auto_refresh_missing_config_warns_with_retry_guidance(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    runtime = _runtime(tmp_path)
    screen = HomeScreen(runtime_context=runtime)
    fake_app = _FakeApp()
    widgets: dict[str, object] = {
        "#jobs-table": _FakeTable(),
        "#home-status": _FakeStatic(),
        "#run-jobs": _FakeButton(),
    }

    monkeypatch.setattr(HomeScreen, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        screen,
        "query_one",
        lambda selector, _=None: widgets[str(selector)],
    )

    ok = screen._refresh_jobs_area(reason="auto")

    assert ok is False
    assert fake_app.notifications[-1][1] == "warning"
    message = fake_app.notifications[-1][0]
    assert "Refresh" in message or "重新整理" in message


def test_home_deferred_auto_refresh_failure_clears_pending(
    tmp_path: Path,
) -> None:
    screen = _TestableHomeScreen(runtime_context=_runtime(tmp_path))
    screen.home_active = True
    screen.refresh_result = False
    screen._pending_auto_refresh = True

    screen._set_job_running_state(False)

    assert screen.refresh_reasons == ["auto"]
    assert screen._pending_auto_refresh is False


def test_home_running_state_updates_dominant_actions(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    runtime = _runtime(tmp_path)
    screen = HomeScreen(runtime_context=runtime)
    run_button = _FakeButton()
    stop_button = _FakeButton()
    refresh_button = _FakeButton()
    widgets: dict[str, object] = {
        "#run-jobs": run_button,
        "#stop-jobs": stop_button,
        "#refresh-jobs": refresh_button,
    }
    started: list[bool] = []
    stopped: list[bool] = []

    monkeypatch.setattr(
        screen,
        "query_one",
        lambda selector, _=None: widgets[str(selector)],
    )
    monkeypatch.setattr(screen, "_start_jobs_animation", lambda: started.append(True))
    monkeypatch.setattr(screen, "_stop_jobs_animation", lambda: stopped.append(True))

    screen._apply_running_state_to_controls(is_running=True)

    assert run_button.disabled is True
    assert run_button.variant == "default"
    assert stop_button.disabled is False
    assert stop_button.variant == "error"
    assert refresh_button.variant == "default"
    assert started == [True]

    screen._apply_running_state_to_controls(is_running=False)

    assert run_button.disabled is False
    assert run_button.variant == "primary"
    assert stop_button.disabled is True
    assert stop_button.variant == "default"
    assert refresh_button.variant == "default"
    assert stopped == [True]
