import gettext
from pathlib import Path
from typing import Any

import yaml
from textual.widgets import Button

from outlook_mail_extractor import i18n as i18n_module
from outlook_mail_extractor.i18n import set_language
from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths
from outlook_mail_extractor.screens import MainConfigTab, PluginConfigEditorModal
from outlook_mail_extractor.screens.modals.add_job import AddJobScreen
from outlook_mail_extractor.ui_schema import schema_text


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


def test_main_config_validate_config_payload_runs_runtime_validation(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._ui_schema = {"validation_rules": []}

    sanitized, failed_errors, failed_warnings = tab._validate_config_payload(
        {"body_max_length": 1200}
    )

    assert sanitized == {"body_max_length": 1200}
    assert failed_warnings == []
    assert "Config missing 'jobs' field" in failed_errors


def test_main_config_validate_config_payload_collects_schema_warning(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
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
    sanitized, failed_errors, failed_warnings = tab._validate_config_payload(payload)

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
    tab._schema_errors = []
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        tab,
        "_runtime_plugin_options",
        lambda: ["download_attachments", "summary_file"],
    )
    monkeypatch.setattr(tab, "_load_raw_config", lambda: {"jobs": []})

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
        "_load_raw_config",
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
        "_load_raw_config",
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


def test_main_config_general_settings_schema_uses_fixed_owned_keys(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))

    schema = tab._general_settings_schema()

    fields = schema["fields"]
    assert set(fields.keys()) == {"body_max_length", "llm_mode", "plugin_modules"}
    assert fields["plugin_modules"]["type"] == "list[str]"


def test_main_config_general_settings_schema_overrides_schema_labels_with_owned_i18n(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._ui_schema = {
        "fields": {
            "body_max_length": {
                "type": "int",
                "label": "自訂長度",
                "required": True,
            },
            "llm_mode": {
                "type": "select",
                "label": "Custom LLM",
                "label_key": "custom.llm.key",
            },
            "plugin_modules": {
                "type": "textarea",
                "label": "自訂模組",
            },
        }
    }

    schema = tab._general_settings_schema()
    fields = schema["fields"]

    assert (
        fields["body_max_length"]["label_key"]
        == "ui.main.general.field.body_max_length"
    )
    assert fields["body_max_length"]["label"] == "Body Max Length"
    assert fields["body_max_length"]["required"] is True

    assert fields["llm_mode"]["label_key"] == "ui.main.general.field.llm_mode"
    assert fields["llm_mode"]["label"] == "LLM Mode"

    assert (
        fields["plugin_modules"]["label_key"] == "ui.main.general.field.plugin_modules"
    )
    assert fields["plugin_modules"]["label"] == "Plugin Modules"
    assert fields["plugin_modules"]["type"] == "list[str]"


def test_main_config_general_settings_schema_falls_back_for_missing_or_invalid_specs(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._ui_schema = {
        "fields": {
            "body_max_length": "invalid",
            "plugin_modules": {"required": True},
        }
    }

    schema = tab._general_settings_schema()
    fields = schema["fields"]

    assert fields["body_max_length"]["label"] == "Body Max Length"
    assert fields["llm_mode"]["label"] == "LLM Mode"
    assert fields["plugin_modules"]["label"] == "Plugin Modules"
    assert fields["plugin_modules"]["required"] is True


def test_main_config_general_settings_schema_renders_labels_by_locale(
    tmp_path: Path,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._ui_schema = {
        "fields": {
            "body_max_length": {"label": "schema-only"},
        }
    }
    field = tab._general_settings_schema()["fields"]["body_max_length"]

    try:
        set_language("en-US")
        assert schema_text(field, "label_key", "label", "") == "Body Max Length"

        set_language("zh-TW")
        assert schema_text(field, "label_key", "label", "") == "內文長度上限"
    finally:
        set_language("en-US")


def test_main_config_general_settings_schema_uses_english_fallback_when_locale_missing(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    field = tab._general_settings_schema()["fields"]["body_max_length"]

    monkeypatch.setattr(i18n_module, "_TRANSLATION", gettext.NullTranslations())
    monkeypatch.setattr(
        i18n_module,
        "_load_yaml_translations",
        lambda language: (
            {}
            if language == "zh-TW"
            else {"ui.main.general.field.body_max_length": "Body Max Length"}
        ),
    )

    try:
        set_language("zh-TW")
        assert schema_text(field, "label_key", "label", "") == "Body Max Length"
    finally:
        set_language("en-US")


def test_main_config_open_general_settings_pushes_modal(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._schema_errors = []
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        tab,
        "_load_general_settings_payload",
        lambda: {"body_max_length": 2000, "llm_mode": "per_plugin"},
    )

    tab._open_general_settings()

    assert len(fake_app.pushed_screens) == 1
    screen = fake_app.pushed_screens[0][0]
    assert isinstance(screen, PluginConfigEditorModal)


def test_main_config_open_general_settings_localizes_modal_title_and_entity(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._schema_errors = []
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(tab, "_load_general_settings_payload", lambda: {})

    try:
        set_language("en-US")
        tab._open_general_settings()
        screen_en = fake_app.pushed_screens[-1][0]
        assert isinstance(screen_en, PluginConfigEditorModal)
        assert screen_en._plugin_name == "Main Config"
        assert screen_en._entity_label == "General"

        set_language("zh-TW")
        tab._open_general_settings()
        screen_zh = fake_app.pushed_screens[-1][0]
        assert isinstance(screen_zh, PluginConfigEditorModal)
        assert screen_zh._plugin_name == "主設定"
        assert screen_zh._entity_label == "一般設定"
    finally:
        set_language("en-US")


def test_main_config_attempt_save_general_settings_preserves_unknown_keys(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    runtime.paths.config_file.write_text(
        yaml.safe_dump(
            {
                "jobs": [
                    {
                        "name": "job-a",
                        "account": "a@example.com",
                        "source": "Inbox",
                    }
                ],
                "body_max_length": 1000,
                "custom_top": "keep-me",
                "custom_nested": {"x": 1},
            },
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    tab = MainConfigTab(runtime_context=runtime)
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(tab, "_load_config", lambda: None)

    saved, error = tab._attempt_save_general_settings(
        {
            "body_max_length": 2500,
            "llm_mode": "per_plugin",
            "plugin_modules": ["custom_plugins.extra"],
        }
    )

    assert saved is True
    assert error is None
    data = yaml.safe_load(runtime.paths.config_file.read_text(encoding="utf-8"))
    assert data["body_max_length"] == 2500
    assert data["llm_mode"] == "per_plugin"
    assert data["plugin_modules"] == ["custom_plugins.extra"]
    assert data["custom_top"] == "keep-me"
    assert data["custom_nested"] == {"x": 1}


def test_main_config_attempt_save_general_settings_warns_when_refresh_fails(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    runtime.paths.config_file.write_text(
        yaml.safe_dump(
            {
                "jobs": [
                    {
                        "name": "job-a",
                        "account": "a@example.com",
                        "source": "Inbox",
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    tab = MainConfigTab(runtime_context=runtime)
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        tab,
        "_load_config",
        lambda: (_ for _ in ()).throw(RuntimeError("refresh failed")),
    )

    saved, error = tab._attempt_save_general_settings(
        {
            "body_max_length": 2200,
            "llm_mode": "per_plugin",
            "plugin_modules": [],
        }
    )

    assert saved is True
    assert error is None
    assert any(
        severity == "warning" and "refresh" in message.lower()
        for message, severity in fake_app.notifications
    )


def test_main_config_remove_job_failure_restores_button_state(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = MainConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._selected_job_index = 0
    fake_app = _FakeApp()
    monkeypatch.setattr(MainConfigTab, "app", property(lambda _self: fake_app))
    monkeypatch.setattr(
        tab,
        "_load_raw_config",
        lambda: {
            "jobs": [
                {
                    "name": "job-a",
                    "account": "a@example.com",
                    "source": "Inbox",
                }
            ]
        },
    )
    monkeypatch.setattr(
        tab,
        "_persist_job_mutation",
        lambda _mutate: (False, "boom", []),
    )
    trigger_button = Button("Remove")

    tab._remove_job(trigger_button)

    assert trigger_button.disabled is False
    assert tab._is_removing_job is False
    assert tab._selected_job_index == 0
    assert fake_app.notifications[-1][1] == "error"
