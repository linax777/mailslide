from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from outlook_mail_extractor.llm import load_llm_config
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


class _FakeTable:
    def __init__(self) -> None:
        self.columns: list[str] = []
        self.rows: list[tuple[str, str]] = []

    def clear(self) -> None:
        self.columns = []
        self.rows = []

    def add_columns(self, *columns: str) -> None:
        self.columns.extend(columns)

    def add_row(self, item: str, value: str) -> None:
        self.rows.append((item, value))


class _FakeStatic:
    def __init__(self) -> None:
        self.value = ""

    def update(self, value: str) -> None:
        self.value = value


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


def test_llm_config_tab_write_file_with_backup(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    target = runtime.paths.llm_config_file
    target.write_text(
        "api_base: http://localhost:11434/v1\ntimeout: 30\n", encoding="utf-8"
    )

    stored: dict[str, Any] = {}

    def fake_store(api_key: str, secret_path: Path) -> Path:
        stored["api_key"] = api_key
        secret_path.write_bytes(b"ciphertext")
        return secret_path

    def fake_clear(secret_path: Path) -> None:
        stored["cleared"] = secret_path

    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.llm_tab.store_llm_api_key",
        fake_store,
    )
    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.llm_tab.clear_llm_api_key",
        fake_clear,
    )

    tab = LLMConfigTab(runtime_context=runtime)
    written = tab._write_llm_config_file(
        {
            "api_base": "http://localhost:11434/v1",
            "api_key": "sk-test",
            "model": "llama3",
            "timeout": 60,
        }
    )

    assert written == target
    content = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert content["timeout"] == 60
    assert content["api_key"] == ""
    assert stored["api_key"] == "sk-test"
    assert (runtime.paths.config_dir / "llm-api-key.bin").exists()

    backup = runtime.paths.config_dir / "llm-config.yaml.bak"
    assert backup.exists()
    assert (
        backup.read_text(encoding="utf-8")
        == "api_base: http://localhost:11434/v1\ntimeout: 30\n"
    )


def test_load_llm_config_reads_api_key_from_secret_file(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "llm-config.yaml"
    config_file.write_text(
        'api_base: http://localhost:11434/v1\napi_key: ""\nmodel: llama3\ntimeout: 30\n',
        encoding="utf-8",
    )
    secret_file = config_dir / "llm-api-key.bin"
    secret_file.write_bytes(b"ciphertext")

    monkeypatch.setattr(
        "outlook_mail_extractor.llm.load_llm_api_key",
        lambda _path: "sk-from-secret",
    )

    loaded = load_llm_config(str(config_file))

    assert loaded.api_key == "sk-from-secret"


def test_llm_config_tab_preserves_existing_secret_when_api_key_blank(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    runtime.paths.llm_config_file.write_text(
        'api_base: http://localhost:11434/v1\napi_key: ""\nmodel: llama3\ntimeout: 30\n',
        encoding="utf-8",
    )
    secret_file = runtime.paths.config_dir / "llm-api-key.bin"
    secret_file.write_bytes(b"ciphertext")

    state: dict[str, bool] = {"cleared": False}

    def fake_store(_api_key: str, _secret_path: Path) -> Path:
        raise AssertionError("store should not be called")

    def fake_clear(_secret_path: Path) -> None:
        state["cleared"] = True

    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.llm_tab.store_llm_api_key",
        fake_store,
    )
    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.llm_tab.clear_llm_api_key",
        fake_clear,
    )

    tab = LLMConfigTab(runtime_context=runtime)
    tab._write_llm_config_file(
        {
            "api_base": "http://localhost:11434/v1",
            "api_key": "",
            "model": "llama3.1",
            "timeout": 45,
        }
    )

    assert state["cleared"] is False
    assert secret_file.exists()


def test_llm_config_tab_scrubs_plaintext_api_key_before_backup(
    tmp_path: Path, monkeypatch
) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    runtime.paths.llm_config_file.write_text(
        'api_base: http://localhost:11434/v1\napi_key: "sk-old"\nmodel: llama3\ntimeout: 30\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.llm_tab.store_llm_api_key",
        lambda _api_key, secret_path: secret_path,
    )
    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.llm_tab.clear_llm_api_key",
        lambda _secret_path: None,
    )

    tab = LLMConfigTab(runtime_context=runtime)
    tab._write_llm_config_file(
        {
            "api_base": "http://localhost:11434/v1",
            "api_key": "sk-new",
            "model": "llama3.1",
            "timeout": 45,
        }
    )

    backup = runtime.paths.config_dir / "llm-config.yaml.bak"
    backup_payload = yaml.safe_load(backup.read_text(encoding="utf-8"))
    assert backup_payload["api_key"] == ""


def test_llm_config_tab_load_uses_table_without_yaml_text_area(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.config_dir.mkdir(parents=True, exist_ok=True)
    runtime.paths.llm_config_file.write_text(
        "api_base: http://localhost:11434/v1\nmodel: llama3\ntimeout: 30\n",
        encoding="utf-8",
    )

    tab = LLMConfigTab(runtime_context=runtime)
    fake_table = _FakeTable()
    fake_title = _FakeStatic()

    def _query_one(selector: str, _=None):
        if selector == "#llm-table":
            return fake_table
        if selector == "#llm-config-title":
            return fake_title
        raise AssertionError(f"unexpected selector: {selector}")

    monkeypatch.setattr(tab, "query_one", _query_one)
    monkeypatch.setattr(
        "outlook_mail_extractor.screens.config.llm_tab.load_llm_config",
        lambda _path: SimpleNamespace(
            api_base="http://localhost:11434/v1",
            api_key="",
            model="llama3",
            timeout=30,
        ),
    )

    tab._load_llm_config()

    assert len(fake_table.rows) == 4
    assert fake_title.value


def test_llm_config_tab_inline_status_renders_success_metadata(tmp_path: Path) -> None:
    tab = LLMConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._last_test_outcome = "success"
    tab._last_success_at = datetime(2026, 4, 2, 10, 30, 0)
    tab._last_success_latency_ms = 321
    tab._latest_test_error = None

    content = tab._render_inline_test_status()

    assert "2026-04-02" in content
    assert "321" in content


def test_llm_config_tab_inline_status_keeps_last_success_when_latest_test_fails(
    tmp_path: Path,
) -> None:
    tab = LLMConfigTab(runtime_context=_runtime_context(tmp_path))
    tab._last_success_at = datetime(2026, 4, 2, 10, 30, 0)
    tab._last_success_latency_ms = 500
    tab._last_test_outcome = "failed"
    tab._latest_test_error = "network down"

    content = tab._render_inline_test_status()

    assert "2026-04-02" in content
    assert "500" in content
    assert "network down" in content


def test_llm_config_tab_update_inline_status_updates_widget(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    tab = LLMConfigTab(runtime_context=_runtime_context(tmp_path))
    widget = _FakeStatic()
    tab._last_test_outcome = "failed"
    tab._latest_test_error = "timeout"

    monkeypatch.setattr(
        tab,
        "query_one",
        lambda selector, _=None: widget if selector == "#llm-test-status" else None,
    )

    tab._update_inline_test_status()

    assert "timeout" in widget.value
