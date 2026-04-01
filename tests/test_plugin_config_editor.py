import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml

from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths
from outlook_mail_extractor.screens import PluginConfigEditorModal, PluginsConfigTab


class _FakeInput:
    def __init__(self, value: str):
        self.value = value


class _FakeTextArea:
    def __init__(self, text: str):
        self.text = text


class _FakeSwitch:
    def __init__(self, value: bool):
        self.value = value


class _FakeSelectionList:
    def __init__(self, selected: list[str]):
        self.selected = selected


class _FakeStatic:
    def __init__(self) -> None:
        self.content = ""

    def update(self, content: str) -> None:
        self.content = content


class _FakeButton:
    def __init__(self) -> None:
        self.disabled = False


class _FakeDataTable:
    def __init__(self) -> None:
        self.columns: tuple[str, ...] = ()
        self.rows: list[tuple[str, str]] = []

    def clear(self) -> None:
        self.rows = []

    def add_columns(self, *columns: str) -> None:
        self.columns = columns

    def add_row(self, col1: str, col2: str) -> None:
        self.rows.append((col1, col2))


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


def _runtime_context(tmp_path: Path) -> RuntimeContext:
    config_dir = tmp_path / "config"
    plugins_dir = config_dir / "plugins"
    paths = RuntimePaths(
        project_root=tmp_path,
        config_dir=config_dir,
        config_file=config_dir / "config.yaml",
        llm_config_file=config_dir / "llm-config.yaml",
        plugins_dir=plugins_dir,
        logging_config_file=config_dir / "logging.yaml",
        logs_dir=tmp_path / "logs",
        readme_file=tmp_path / "README.md",
    )
    return RuntimeContext(
        paths=paths,
        logger_manager=_FakeLoggerManager(),
        client_factory=lambda: None,
    )


def test_plugin_config_editor_collect_payload_success() -> None:
    schema: dict[str, Any] = {
        "fields": {
            "enabled": {"type": "bool", "required": True},
            "output_file": {"type": "path", "required": True},
            "response_format": {
                "type": "select",
                "required": True,
                "options": ["json", "text"],
            },
            "include_fields": {"type": "list[str]", "required": True},
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal("event_table", schema, {})

    widgets: dict[str, Any] = {
        "plugin-field-enabled": _FakeSwitch(value=True),
        "plugin-field-output_file": _FakeInput(value="output/events.csv"),
        "plugin-field-response_format": _FakeSelectionList(selected=["json"]),
        "plugin-field-include_fields": _FakeTextArea("subject\nsender\n"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    payload = modal._collect_payload()

    assert payload == {
        "enabled": True,
        "output_file": "output/events.csv",
        "response_format": "json",
        "include_fields": ["subject", "sender"],
    }


def test_plugin_config_editor_path_field_resolves_to_absolute_with_base_dir(
    tmp_path: Path,
) -> None:
    schema: dict[str, Any] = {
        "fields": {
            "output_file": {"type": "path", "required": True},
        },
        "validation_rules": [],
    }
    base_dir = tmp_path / "config"
    modal = PluginConfigEditorModal(
        "event_table",
        schema,
        {"output_file": "output/events.xlsx"},
        base_dir=base_dir,
    )

    resolved = modal._resolve_initial_text(
        "output_file", schema["fields"]["output_file"]
    )

    assert resolved == str((base_dir / "output" / "events.xlsx").resolve())


def test_plugin_config_editor_path_field_keeps_relative_without_base_dir() -> None:
    schema: dict[str, Any] = {
        "fields": {
            "output_file": {"type": "path", "required": True},
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "event_table",
        schema,
        {"output_file": "output/events.xlsx"},
    )

    resolved = modal._resolve_initial_text(
        "output_file", schema["fields"]["output_file"]
    )

    assert resolved == str(Path("output/events.xlsx"))


def test_plugin_config_editor_output_dir_field_resolves_with_base_dir(
    tmp_path: Path,
) -> None:
    schema: dict[str, Any] = {
        "fields": {
            "output_dir": {"type": "path", "required": True},
        },
        "validation_rules": [],
    }
    base_dir = tmp_path / "config"
    modal = PluginConfigEditorModal(
        "download_attachments",
        schema,
        {"output_dir": "output/attachments"},
        base_dir=base_dir,
    )

    resolved = modal._resolve_initial_text("output_dir", schema["fields"]["output_dir"])

    assert resolved == str((base_dir / "output" / "attachments").resolve())


def test_plugin_config_editor_collect_payload_invalid_int() -> None:
    schema = {
        "fields": {
            "timeout": {
                "type": "int",
                "required": True,
                "label": "逾時",
            }
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal("demo", schema, {})
    widgets: dict[str, Any] = {
        "plugin-field-timeout": _FakeInput(value="abc"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    with pytest.raises(ValueError, match=r"(逾時 必須是整數|逾時 must be an integer)"):
        modal._collect_payload()


def test_plugins_config_tab_write_plugin_file_with_backup(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.plugins_dir.mkdir(parents=True, exist_ok=True)
    target = runtime.paths.plugins_dir / "demo.yaml"
    target.write_text("enabled: false\n", encoding="utf-8")

    tab = PluginsConfigTab(runtime_context=runtime)
    path = tab._write_plugin_config_file("demo", {"enabled": True})

    assert path == target
    content = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert content == {"enabled": True}

    backup = runtime.paths.plugins_dir / "demo.yaml.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "enabled: false\n"


def test_plugin_config_editor_response_json_format_non_time_fields_editable() -> None:
    schema = {
        "fields": {
            "enabled": {"type": "bool", "required": True},
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "summary_file",
        schema,
        {
            "enabled": True,
            "response_json_format": {
                "has_summary": '{"action":"summary","summary":"old"}',
            },
        },
    )

    widgets: dict[str, Any] = {
        "plugin-field-enabled": _FakeSwitch(value=True),
        "plugin-jsonfmt-has_summary-summary": _FakeInput(value="new"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    payload = modal._collect_payload()

    assert payload["enabled"] is True
    formatted = payload["response_json_format"]
    assert isinstance(formatted, dict)
    parsed = json.loads(formatted["has_summary"])
    assert parsed == {"action": "summary", "summary": "new"}


def test_plugin_config_editor_response_json_time_fields_are_locked() -> None:
    schema = {
        "fields": {
            "enabled": {"type": "bool", "required": True},
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "event_table",
        schema,
        {
            "enabled": True,
            "response_json_format": {
                "create_true": '{"action":"appointment","create":true,"start":"2024-01-15T14:00:00","end":"2024-01-15T15:00:00"}',
            },
        },
    )

    widgets: dict[str, Any] = {
        "plugin-field-enabled": _FakeSwitch(value=True),
        "plugin-jsonfmt-create_true-create": _FakeSwitch(value=False),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    payload = modal._collect_payload()

    formatted = payload["response_json_format"]
    assert isinstance(formatted, dict)
    parsed = json.loads(formatted["create_true"])
    assert parsed["action"] == "appointment"
    assert parsed["create"] is False
    assert parsed["start"] == "2024-01-15T14:00:00"
    assert parsed["end"] == "2024-01-15T15:00:00"


def test_plugins_config_tab_load_plugins_ignores_backup_files(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.plugins_dir.mkdir(parents=True, exist_ok=True)

    (runtime.paths.plugins_dir / "event_table.yaml.sample").write_text(
        "enabled: true\n", encoding="utf-8"
    )
    (runtime.paths.plugins_dir / "event_table.yaml").write_text(
        "enabled: false\n", encoding="utf-8"
    )
    (runtime.paths.plugins_dir / "event_table.yaml.bak").write_text(
        "enabled: true\n", encoding="utf-8"
    )
    (runtime.paths.plugins_dir / "summary_file.yaml.bak").write_text(
        "enabled: true\n", encoding="utf-8"
    )

    tab = PluginsConfigTab(runtime_context=runtime)
    title = _FakeStatic()
    table = _FakeDataTable()
    edit_button = _FakeButton()

    widgets: dict[str, Any] = {
        "plugin-list-title": title,
        "plugin-list": table,
        "edit-plugin": edit_button,
    }
    tab.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    tab._load_plugins()

    assert table.rows == [("event_table", "active")]
    assert title.content in ("📦 Plugins (1 個)", "📦 Plugins (1)")


def test_plugins_config_tab_cleanup_backup_files(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.plugins_dir.mkdir(parents=True, exist_ok=True)

    backup1 = runtime.paths.plugins_dir / "event_table.yaml.bak"
    backup2 = runtime.paths.plugins_dir / "summary_file.yaml.bak"
    active = runtime.paths.plugins_dir / "event_table.yaml"
    backup1.write_text("enabled: true\n", encoding="utf-8")
    backup2.write_text("enabled: true\n", encoding="utf-8")
    active.write_text("enabled: false\n", encoding="utf-8")

    tab = PluginsConfigTab(runtime_context=runtime)
    removed, failed = tab._cleanup_backup_files()

    assert removed == 2
    assert failed == []
    assert not backup1.exists()
    assert not backup2.exists()
    assert active.exists()


def test_plugin_config_editor_yaml_field_parses_dict() -> None:
    from outlook_mail_extractor.screens.modals.plugin_config_editor import (
        PluginConfigEditorModal,
    )

    schema = {
        "fields": {
            "enabled": {"type": "bool", "required": True},
            "prompt_profiles": {
                "type": "yaml",
                "label": "Prompt Profiles",
                "required": False,
            },
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "add_category",
        schema,
        {"enabled": True},
    )

    yaml_text = "general_v1:\n  version: 1\n  system_prompt: |\n    你是一個助手\n"
    widgets: dict[str, Any] = {
        "plugin-field-enabled": _FakeSwitch(value=True),
        "plugin-field-prompt_profiles": _FakeTextArea(yaml_text),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    payload = modal._collect_payload()

    assert payload["enabled"] is True
    profiles = payload["prompt_profiles"]
    assert isinstance(profiles, dict)
    assert "general_v1" in profiles
    assert profiles["general_v1"]["version"] == 1
    assert profiles["general_v1"]["system_prompt"].rstrip("\n") == "你是一個助手"


def test_plugin_config_editor_yaml_field_empty_returns_none() -> None:
    from outlook_mail_extractor.screens.modals.plugin_config_editor import (
        PluginConfigEditorModal,
    )

    schema = {
        "fields": {
            "prompt_profiles": {"type": "yaml", "label": "Profiles", "required": False},
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal("add_category", schema, {})

    widgets: dict[str, Any] = {
        "plugin-field-prompt_profiles": _FakeTextArea(""),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    payload = modal._collect_payload()

    assert "prompt_profiles" not in payload


def test_plugin_config_editor_yaml_field_invalid_raises() -> None:
    from outlook_mail_extractor.screens.modals.plugin_config_editor import (
        PluginConfigEditorModal,
    )

    schema = {
        "fields": {
            "prompt_profiles": {"type": "yaml", "label": "Profiles", "required": False},
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal("add_category", schema, {})

    widgets: dict[str, Any] = {
        "plugin-field-prompt_profiles": _FakeTextArea("invalid: yaml: : :"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    with pytest.raises(
        ValueError,
        match=r"(不是有效的 YAML|is not valid YAML)",
    ):
        modal._collect_payload()


def test_plugin_config_editor_prompt_profile_key_rename_success() -> None:
    schema = {
        "fields": {
            "prompt_profiles": {
                "type": "yaml",
                "label": "Prompt Profiles",
                "required": False,
            },
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "add_category",
        schema,
        {
            "prompt_profiles": {
                "general_v1": {
                    "version": 1,
                    "description": "General",
                    "system_prompt": "hello",
                }
            }
        },
    )

    widgets: dict[str, Any] = {
        "plugin-prompt-key": _FakeInput("invoice_v2"),
        "plugin-prompt-version": _FakeInput("2"),
        "plugin-prompt-description": _FakeInput("Invoice"),
        "plugin-prompt-system_prompt": _FakeTextArea("invoice prompt"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    modal._save_active_prompt_profile_fields()

    assert modal._active_prompt_profile == "invoice_v2"
    assert modal._prompt_profile_order == ["invoice_v2"]
    assert "general_v1" not in modal._prompt_profiles_state
    assert modal._prompt_profiles_state["invoice_v2"]["version"] == 2
    assert modal._prompt_profile_renames == {"general_v1": "invoice_v2"}


def test_plugin_config_editor_prompt_profile_key_required() -> None:
    schema = {
        "fields": {
            "prompt_profiles": {
                "type": "yaml",
                "label": "Prompt Profiles",
                "required": False,
            },
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "add_category",
        schema,
        {
            "prompt_profiles": {
                "general_v1": {
                    "version": 1,
                    "description": "General",
                    "system_prompt": "hello",
                }
            }
        },
    )

    widgets: dict[str, Any] = {
        "plugin-prompt-key": _FakeInput("  "),
        "plugin-prompt-version": _FakeInput("1"),
        "plugin-prompt-description": _FakeInput("General"),
        "plugin-prompt-system_prompt": _FakeTextArea("hello"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    with pytest.raises(
        ValueError, match=r"(Profile Key 為必填|Profile Key is required)"
    ):
        modal._save_active_prompt_profile_fields()


def test_plugin_config_editor_prompt_profile_key_duplicate() -> None:
    schema = {
        "fields": {
            "prompt_profiles": {
                "type": "yaml",
                "label": "Prompt Profiles",
                "required": False,
            },
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "add_category",
        schema,
        {
            "prompt_profiles": {
                "general_v1": {
                    "version": 1,
                    "description": "General",
                    "system_prompt": "hello",
                },
                "invoice_v1": {
                    "version": 1,
                    "description": "Invoice",
                    "system_prompt": "invoice",
                },
            }
        },
    )

    widgets: dict[str, Any] = {
        "plugin-prompt-key": _FakeInput("invoice_v1"),
        "plugin-prompt-version": _FakeInput("1"),
        "plugin-prompt-description": _FakeInput("General"),
        "plugin-prompt-system_prompt": _FakeTextArea("hello"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    with pytest.raises(
        ValueError,
        match=r"(Profile Key already exists|Profile Key 已存在)",
    ):
        modal._save_active_prompt_profile_fields()


def test_plugin_config_editor_collect_payload_applies_profile_rename_to_default() -> (
    None
):
    schema = {
        "fields": {
            "default_prompt_profile": {
                "type": "str",
                "required": False,
            },
            "prompt_profiles": {
                "type": "yaml",
                "label": "Prompt Profiles",
                "required": False,
            },
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        "add_category",
        schema,
        {
            "default_prompt_profile": "general_v1",
            "prompt_profiles": {
                "general_v1": {
                    "version": 1,
                    "description": "General",
                    "system_prompt": "hello",
                }
            },
        },
    )

    widgets: dict[str, Any] = {
        "plugin-field-default_prompt_profile": _FakeInput("general_v1"),
        "plugin-prompt-key": _FakeInput("invoice_v2"),
        "plugin-prompt-version": _FakeInput("2"),
        "plugin-prompt-description": _FakeInput("Invoice"),
        "plugin-prompt-system_prompt": _FakeTextArea("invoice prompt"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    payload = modal._collect_payload()

    assert payload["default_prompt_profile"] == "invoice_v2"
    assert payload["_prompt_profile_renames"] == {"general_v1": "invoice_v2"}
    profiles = payload["prompt_profiles"]
    assert isinstance(profiles, dict)
    assert "invoice_v2" in profiles


def test_plugins_config_tab_sync_job_prompt_profile_refs(tmp_path: Path) -> None:
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
                        "plugin_prompt_profiles": {
                            "add_category": "general_v1",
                            "move_to_folder": "routing_v1",
                        },
                    },
                    {
                        "name": "job-b",
                        "account": "b@example.com",
                        "source": "Inbox",
                        "plugin_prompt_profiles": {
                            "add_category": "general_v1",
                        },
                    },
                ]
            },
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )

    tab = PluginsConfigTab(runtime_context=runtime)
    updated = tab._sync_job_prompt_profile_refs(
        "add_category",
        {"general_v1": "invoice_v2"},
    )

    assert updated == 2

    loaded = yaml.safe_load(runtime.paths.config_file.read_text(encoding="utf-8"))
    assert loaded["jobs"][0]["plugin_prompt_profiles"]["add_category"] == "invoice_v2"
    assert loaded["jobs"][1]["plugin_prompt_profiles"]["add_category"] == "invoice_v2"
    assert loaded["jobs"][0]["plugin_prompt_profiles"]["move_to_folder"] == "routing_v1"

    backup = runtime.paths.config_dir / "config.yaml.bak"
    assert backup.exists()


def test_plugins_config_tab_infer_prompt_profile_rename_from_payload(
    tmp_path: Path,
) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.plugins_dir.mkdir(parents=True, exist_ok=True)
    (runtime.paths.plugins_dir / "add_category.yaml").write_text(
        yaml.safe_dump(
            {
                "prompt_profiles": {
                    "general_v1": {
                        "version": 1,
                        "description": "General",
                        "system_prompt": "hello",
                    }
                }
            },
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )

    tab = PluginsConfigTab(runtime_context=runtime)
    inferred = tab._infer_prompt_profile_renames(
        "add_category",
        {
            "prompt_profiles": {
                "invoice_v2": {
                    "version": 1,
                    "description": "General",
                    "system_prompt": "hello",
                }
            }
        },
    )

    assert inferred == {"general_v1": "invoice_v2"}


def test_plugin_config_editor_cancel_button_dismisses_modal() -> None:
    schema: dict[str, Any] = {"fields": {}, "validation_rules": []}
    modal = PluginConfigEditorModal("demo", schema, {})
    dismissed: list[dict[str, Any] | None] = []

    def _dismiss(payload: dict[str, Any] | None) -> None:
        dismissed.append(payload)

    modal.dismiss = cast(Any, _dismiss)  # type: ignore[method-assign]

    event = SimpleNamespace(button=SimpleNamespace(id="plugin-editor-cancel"))
    modal.on_button_pressed(cast(Any, event))

    assert dismissed == [None]


def test_plugin_config_editor_save_shows_error_when_payload_invalid() -> None:
    schema: dict[str, Any] = {"fields": {}, "validation_rules": []}
    modal = PluginConfigEditorModal("demo", schema, {})
    errors: list[str] = []

    def _raise_invalid_payload() -> dict[str, Any]:
        raise ValueError("invalid payload")

    modal._collect_payload = _raise_invalid_payload  # type: ignore[method-assign]
    modal._show_error = lambda message: errors.append(message)  # type: ignore[method-assign]

    event = SimpleNamespace(button=SimpleNamespace(id="plugin-editor-save"))
    modal.on_button_pressed(cast(Any, event))

    assert errors == ["invalid payload"]
