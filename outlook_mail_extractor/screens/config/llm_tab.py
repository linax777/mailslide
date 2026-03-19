"""LLM config tab."""

import re
from pathlib import Path
from typing import Any

import yaml
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static, TextArea

from ...llm import load_llm_config
from ...runtime import RuntimeContext, get_runtime_context
from ...ui_schema import (
    evaluate_rules,
    load_ui_schema,
    strip_reserved_metadata,
    validate_ui_schema,
)
from .io_helpers import write_yaml_with_backup
from .validation_helpers import collect_rule_failures, preview_messages
from ..modals.plugin_config_editor import PluginConfigEditorModal


class LLMConfigTab(Static):
    """LLM 設定分頁"""

    CSS = """
    #llm-help {
        width: 100%;
    }
    #llm-examples {
        width: 100%;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        self._sample_path = self._runtime.paths.llm_config_file.with_suffix(
            ".yaml.sample"
        )
        self._ui_schema = load_ui_schema(self._sample_path)
        self._schema_errors = validate_ui_schema(self._ui_schema)

    def compose(self) -> ComposeResult:
        with Vertical(id="llm-main"):
            yield Static("🤖 LLM 設定 (config/llm-config.yaml)", id="llm-config-title")
            yield TextArea("", id="llm-config-content", read_only=True)
            yield Static("📊 設定值", id="llm-values-title")
            yield DataTable(id="llm-table")
            yield Static("💡 說明", id="llm-help-title")
            yield Static(
                "• API Base: API 伺服器位址 (如 Ollama 本機: http://localhost:11434/v1)\n"
                "• API Key: API 密鑰 (OpenAI 需要，其他可能可留空)\n"
                "• Model: 模型名稱 (如 llama3, gpt-4 等)\n"
                "• Timeout: 請求逾時秒數",
                id="llm-help",
            )
            yield Static("🔌 連線測試", id="llm-test-title")
            yield Static(
                "點擊「測試連線」按鈕驗證 LLM API 是否可正常連線\n"
                "測試會發送一個簡單的請求確認 API 可用性",
                id="llm-test-desc",
            )
            with Horizontal(id="llm-actions"):
                yield Button("🔗 測試連線", id="test-llm-connection", variant="primary")
                yield Button("🛠️ 編輯設定", id="edit-llm-config")

    def on_mount(self) -> None:
        self._load_llm_config()

    def _load_llm_config(self) -> None:
        content_widget = self.query_one("#llm-config-content", TextArea)
        table = self.query_one("#llm-table", DataTable)

        try:
            llm_config_path = self._runtime.paths.llm_config_file
            content = llm_config_path.read_text(encoding="utf-8")
            masked_content = re.sub(r"(api_key:\s*).+", r"\1***", content)
            content_widget.load_text(masked_content)

            llm_config = load_llm_config(str(llm_config_path))
            table.clear()
            table.add_columns("項目", "值")
            table.add_row("API Base", llm_config.api_base)
            table.add_row("API Key", "***" if llm_config.api_key else "(未設定)")
            table.add_row("Model", llm_config.model)
            table.add_row("Timeout", f"{llm_config.timeout} 秒")

            self.query_one("#llm-config-title", Static).update(
                "🤖 LLM 設定 (config/llm-config.yaml) ✅"
            )
        except Exception as e:
            self.query_one("#llm-config-title", Static).update(
                f"🤖 LLM 設定 (config/llm-config.yaml) ❌ {e}"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "test-llm-connection":
            self._test_llm_connection()
            return
        if event.button.id == "edit-llm-config":
            self._open_llm_editor()

    def _load_llm_payload(self) -> dict[str, Any]:
        llm_config_path = self._runtime.paths.llm_config_file
        if not llm_config_path.exists():
            raise FileNotFoundError("找不到 config/llm-config.yaml")

        try:
            with open(llm_config_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"llm-config.yaml YAML 解析錯誤: {e}") from e

        if not isinstance(payload, dict):
            raise ValueError("llm-config.yaml 內容必須是 YAML 物件")
        return payload

    def _open_llm_editor(self) -> None:
        if not self._ui_schema:
            self.app.notify(
                "⚠️ llm-config.yaml.sample 缺少 _ui，維持唯讀模式", severity="warning"
            )
            return

        if self._schema_errors:
            preview = " | ".join(self._schema_errors[:2])
            self.app.notify(f"❌ _ui schema 結構錯誤: {preview}", severity="error")
            return

        try:
            payload = self._load_llm_payload()
        except Exception as e:
            self.app.notify(str(e), severity="error")
            return

        self.app.push_screen(
            PluginConfigEditorModal(
                plugin_name="llm-config",
                schema=self._ui_schema,
                current_config=strip_reserved_metadata(payload),
                entity_label="LLM",
            ),
            self._handle_llm_editor_result,
        )

    def _handle_llm_editor_result(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return

        sanitized = strip_reserved_metadata(result)
        results = evaluate_rules(sanitized, self._ui_schema.get("validation_rules", []))
        failed_errors, failed_warnings = collect_rule_failures(results)

        if failed_errors:
            preview = preview_messages(failed_errors)
            self.app.notify(f"❌ 驗證失敗：{preview}", severity="error")
            return

        try:
            self._write_llm_config_file(sanitized)
            self._load_llm_config()
            if failed_warnings:
                preview = preview_messages(failed_warnings)
                self.app.notify(f"⚠️ 已儲存，請留意：{preview}", severity="warning")
            else:
                self.app.notify("✅ 已儲存 llm-config.yaml", severity="information")
        except Exception as e:
            self.app.notify(f"❌ 儲存失敗: {e}", severity="error")

    def _write_llm_config_file(self, payload: dict[str, Any]) -> Path:
        """Write LLM config and create `.bak` when original exists."""
        return write_yaml_with_backup(
            self._runtime.paths.llm_config_file,
            payload,
        )

    def _test_llm_connection(self) -> None:
        llm_config_path = self._runtime.paths.llm_config_file
        if not llm_config_path.exists():
            self.app.notify(
                "❌ llm-config.yaml 不存在，請先建立設定檔",
                severity="error",
            )
            return

        test_button = self.query_one("#test-llm-connection", Button)
        test_button.disabled = True

        self.app.notify("🔄 開始測試 LLM 連線...")

        self.run_worker(self._execute_test(), exclusive=True)

    async def _execute_test(self) -> None:
        try:
            llm_config = load_llm_config(str(self._runtime.paths.llm_config_file))
            from ...llm import LLMClient

            client = LLMClient(llm_config)
            response = client.chat(
                system_prompt="只用一個詞回覆：OK",
                user_prompt="Hi",
                temperature=0,
            )
            client.close()

            if "ok" in response.lower():
                self.call_later(
                    self.app.notify,
                    "✅ LLM 連線成功！",
                    severity="information",
                )
            else:
                self.call_later(
                    self.app.notify,
                    f"⚠️ LLM 回覆異常: {response[:50]}",
                    severity="warning",
                )
        except Exception as e:
            self.call_later(
                self.app.notify,
                f"❌ LLM 連線失敗: {e}",
                severity="error",
            )
        finally:
            self.call_later(self._enable_button)

    def _enable_button(self) -> None:
        try:
            test_button = self.query_one("#test-llm-connection", Button)
            test_button.disabled = False
        except Exception:
            pass
