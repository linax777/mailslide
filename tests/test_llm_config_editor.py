from pathlib import Path
from typing import Any

import yaml

from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths
from outlook_mail_extractor.screens import LLMConfigTab, PluginConfigEditorModal


class _FakeInput:
    def __init__(self, value: str):
        self.value = value


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


def test_llm_config_editor_collect_secret_and_int_fields() -> None:
    schema = {
        "fields": {
            "api_base": {"type": "str", "required": True},
            "api_key": {"type": "secret", "required": False},
            "timeout": {"type": "int", "required": True, "label": "Timeout"},
        },
        "validation_rules": [],
    }
    modal = PluginConfigEditorModal(
        plugin_name="llm-config",
        schema=schema,
        current_config={},
        entity_label="LLM",
    )

    widgets: dict[str, Any] = {
        "plugin-field-api_base": _FakeInput(value="http://localhost:11434/v1"),
        "plugin-field-api_key": _FakeInput(value="sk-test"),
        "plugin-field-timeout": _FakeInput(value="45"),
    }
    modal.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]

    payload = modal._collect_payload()

    assert payload["api_base"] == "http://localhost:11434/v1"
    assert payload["api_key"] == "sk-test"
    assert payload["timeout"] == 45


def test_llm_config_tab_write_file_with_backup(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    target = runtime.paths.llm_config_file
    target.write_text(
        "api_base: http://localhost:11434/v1\ntimeout: 30\n", encoding="utf-8"
    )

    tab = LLMConfigTab(runtime_context=runtime)
    written = tab._write_llm_config_file(
        {
            "api_base": "http://localhost:11434/v1",
            "api_key": "",
            "model": "llama3",
            "timeout": 60,
        }
    )

    assert written == target
    content = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert content["timeout"] == 60

    backup = runtime.paths.config_dir / "llm-config.yaml.bak"
    assert backup.exists()
    assert (
        backup.read_text(encoding="utf-8")
        == "api_base: http://localhost:11434/v1\ntimeout: 30\n"
    )
