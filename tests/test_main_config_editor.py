from pathlib import Path
from typing import Any

import yaml

from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths
from outlook_mail_extractor.screens import MainConfigTab
from outlook_mail_extractor.screens.modals.add_job import AddJobScreen


class _FakeLoggerManager:
    def set_ui_sink(self, callback: Any) -> None:
        del callback

    def start_session(self, enable_ui_sink: bool = False) -> Path:
        del enable_ui_sink
        return Path("logs/session.log")

    def get_current_log_path(self) -> Path | None:
        return None

    def get_display_level(self) -> str:
        return "INFO"

    def set_display_level(self, level: str) -> None:
        del level


class _FakeApp:
    def __init__(self) -> None:
        self.pushed_screens: list[tuple[object, object]] = []
        self.notifications: list[tuple[str, str]] = []

    def push_screen(self, screen: object, callback: object) -> None:
        self.pushed_screens.append((screen, callback))

    def notify(self, message: object, severity: str = "information") -> None:
        self.notifications.append((str(message), severity))


def _runtime_context(tmp_path: Path) -> RuntimeContext:
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


def test_main_config_validate_editor_payload_runs_runtime_validation(
    tmp_path: Path,
) -> None:
    runtime = _runtime_context(tmp_path)
    tab = MainConfigTab(runtime_context=runtime)
    tab._ui_schema = {"validation_rules": []}

    sanitized, failed_errors, failed_warnings = tab._validate_editor_payload(
        {"body_max_length": 1200}
    )

    assert sanitized == {"body_max_length": 1200}
    assert failed_warnings == []
    assert "Config missing 'jobs' field" in failed_errors


def test_main_config_validate_editor_payload_collects_schema_warning(
    tmp_path: Path,
) -> None:
    runtime = _runtime_context(tmp_path)
    tab = MainConfigTab(runtime_context=runtime)
    tab._ui_schema = {
        "validation_rules": [
            {
                "id": "unique_job_name",
                "level": "warning",
                "message": "name duplicated",
            }
        ]
    }

    payload = {
        "jobs": [
            {"name": "dup", "account": "a@example.com", "source": "Inbox"},
            {"name": "dup", "account": "b@example.com", "source": "Inbox"},
        ]
    }
    sanitized, failed_errors, failed_warnings = tab._validate_editor_payload(payload)

    assert failed_errors == []
    assert failed_warnings == ["name duplicated"]
    assert sanitized == payload


def test_main_config_write_config_file_creates_backup(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    target = runtime.paths.config_file
    target.write_text("jobs: []\nbody_max_length: 1200\n", encoding="utf-8")

    tab = MainConfigTab(runtime_context=runtime)
    written = tab._write_config_file(
        {
            "body_max_length": 2000,
            "jobs": [
                {
                    "name": "job-1",
                    "account": "x@example.com",
                    "source": "Inbox",
                }
            ],
        }
    )

    assert written == target
    content = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert content["body_max_length"] == 2000
    assert content["jobs"][0]["name"] == "job-1"

    backup = runtime.paths.config_dir / "config.yaml.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "jobs: []\nbody_max_length: 1200\n"
    assert not (runtime.paths.config_dir / ".config.yaml.tmp").exists()


def test_main_config_resolve_remove_job_index_prefers_selected(tmp_path: Path) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._selected_job_index = 1

    index = tab._resolve_remove_job_index([{"name": "a"}, {"name": "b"}])

    assert index == 1


def test_main_config_resolve_remove_job_index_falls_back_to_last(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._selected_job_index = 10

    index = tab._resolve_remove_job_index([{"name": "a"}, {"name": "b"}])

    assert index == 1


def test_main_config_resolve_edit_job_index_prefers_selected(tmp_path: Path) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._selected_job_index = 1

    index = tab._resolve_edit_job_index([{"name": "a"}, {"name": "b"}])

    assert index == 1


def test_main_config_resolve_edit_job_index_requires_valid_selection(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._selected_job_index = 10

    index = tab._resolve_edit_job_index([{"name": "a"}, {"name": "b"}])

    assert index is None


def test_main_config_select_job_row_updates_selected_index(tmp_path: Path) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._rendered_job_indices = [3, 5]

    tab._select_job_row(1)

    assert tab._selected_job_index == 5


def test_main_config_select_job_row_invalid_clears_selection(tmp_path: Path) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._rendered_job_indices = [2]
    tab._selected_job_index = 2

    tab._select_job_row(9)

    assert tab._selected_job_index is None


def test_main_config_ensure_reload_button_added_when_missing(tmp_path: Path) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._ui_schema = {"buttons": [{"id": "save", "action": "save"}]}

    tab._ensure_reload_button_in_schema()

    buttons = tab._ui_schema["buttons"]
    assert isinstance(buttons, list)
    reload_buttons = [
        button
        for button in buttons
        if isinstance(button, dict) and button.get("id") == "reload"
    ]
    assert len(reload_buttons) == 1
    assert reload_buttons[0].get("label_key") == "ui.main.button.reload"


def test_main_config_ensure_reload_button_not_duplicated(tmp_path: Path) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._ui_schema = {
        "buttons": [
            {
                "id": "reload",
                "label_key": "ui.main.button.reload",
                "action": "reload",
            }
        ]
    }

    tab._ensure_reload_button_in_schema()

    buttons = tab._ui_schema["buttons"]
    assert isinstance(buttons, list)
    assert (
        len([b for b in buttons if isinstance(b, dict) and b.get("id") == "reload"])
        == 1
    )


def test_main_config_runtime_plugin_options_deduplicates_and_sorts(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))

    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.main_tab.list_plugins",
        lambda: [
            "summary_file",
            " download_attachments ",
            "Download_Attachments",
            "event_table",
            "",
        ],
    )

    assert tab._runtime_plugin_options() == [
        "download_attachments",
        "event_table",
        "summary_file",
    ]


def test_main_config_add_job_uses_runtime_plugin_options(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        tab,
        "_runtime_plugin_options",
        lambda: ["download_attachments", "summary_file"],
    )
    monkeypatch.setattr(tab, "_load_editor_config", lambda: {"jobs": []})

    tab._add_job()

    assert len(fake_app.pushed_screens) == 1
    screen = fake_app.pushed_screens[0][0]
    assert isinstance(screen, AddJobScreen)
    assert screen._plugin_options == ["download_attachments", "summary_file"]


def test_main_config_edit_job_preserves_unavailable_plugin_options(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._selected_job_index = 0
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        tab,
        "_runtime_plugin_options",
        lambda: ["download_attachments", "summary_file"],
    )
    monkeypatch.setattr(
        tab,
        "_load_editor_config",
        lambda: {
            "jobs": [
                {
                    "name": "job-a",
                    "account": "a@example.com",
                    "source": "Inbox",
                    "plugins": ["download_attachments", "legacy_plugin"],
                }
            ]
        },
    )

    tab._edit_job()

    assert len(fake_app.pushed_screens) == 1
    screen = fake_app.pushed_screens[0][0]
    assert isinstance(screen, AddJobScreen)
    assert screen._plugin_options == [
        "download_attachments",
        "summary_file",
        "legacy_plugin",
    ]
    assert screen._unavailable_plugin_keys == {"legacy_plugin"}


def test_main_config_edit_job_ignores_malformed_existing_plugins(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._selected_job_index = 0
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        tab,
        "_runtime_plugin_options",
        lambda: ["download_attachments", "summary_file"],
    )
    monkeypatch.setattr(
        tab,
        "_load_editor_config",
        lambda: {
            "jobs": [
                {
                    "name": "job-a",
                    "account": "a@example.com",
                    "source": "Inbox",
                    "plugins": "legacy_plugin",
                }
            ]
        },
    )

    tab._edit_job()

    assert len(fake_app.pushed_screens) == 1
    screen = fake_app.pushed_screens[0][0]
    assert isinstance(screen, AddJobScreen)
    assert screen._plugin_options == ["download_attachments", "summary_file"]
    assert screen._unavailable_plugin_keys == set()
