import json
from pathlib import Path
from typing import Any

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
    schema = {
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

    with pytest.raises(ValueError, match="逾時 必須是整數"):
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
