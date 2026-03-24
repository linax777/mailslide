"""LLM config tab."""

import re
from pathlib import Path
from typing import Any

import yaml
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static, TextArea

from ...i18n import resolve_language, set_language, t
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
        set_language(resolve_language(self._runtime.paths.config_file))
        self._sample_path = self._runtime.paths.llm_config_file.with_suffix(
            ".yaml.sample"
        )
        self._ui_schema = load_ui_schema(self._sample_path)
        self._schema_errors = validate_ui_schema(self._ui_schema)

    def compose(self) -> ComposeResult:
        with Vertical(id="llm-main"):
            yield Static(t("ui.llm.title"), id="llm-config-title")
            yield TextArea("", id="llm-config-content", read_only=True)
            yield Static(t("ui.llm.values.title"), id="llm-values-title")
            yield DataTable(id="llm-table")
            yield Static(t("ui.llm.help.title"), id="llm-help-title")
            yield Static(
                t("ui.llm.help.body"),
                id="llm-help",
            )
            yield Static(t("ui.llm.test.title"), id="llm-test-title")
            yield Static(
                t("ui.llm.test.desc"),
                id="llm-test-desc",
            )
            with Horizontal(id="llm-actions"):
                yield Button(
                    t("ui.llm.button.test_connection"),
                    id="test-llm-connection",
                    variant="primary",
                )
                yield Button(t("ui.llm.button.edit"), id="edit-llm-config")

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
            table.add_columns(t("ui.common.column.item"), t("ui.common.column.value"))
            table.add_row(t("ui.llm.table.api_base"), llm_config.api_base)
            table.add_row(
                t("ui.llm.table.api_key"),
                "***" if llm_config.api_key else t("ui.llm.table.not_set"),
            )
            table.add_row(t("ui.llm.table.model"), llm_config.model)
            table.add_row(
                t("ui.llm.table.timeout"),
                t("ui.llm.table.timeout_seconds", seconds=llm_config.timeout),
            )

            self.query_one("#llm-config-title", Static).update(t("ui.llm.title.ok"))
        except Exception as e:
            self.query_one("#llm-config-title", Static).update(
                t("ui.llm.title.error", error=e)
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
            raise FileNotFoundError(t("ui.llm.error.config_missing"))

        try:
            with open(llm_config_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(t("ui.llm.error.yaml_parse", error=e)) from e

        if not isinstance(payload, dict):
            raise ValueError(t("ui.llm.error.yaml_object_required"))
        return payload

    def _open_llm_editor(self) -> None:
        if not self._ui_schema:
            self.app.notify(t("ui.llm.notify.schema_missing"), severity="warning")
            return

        if self._schema_errors:
            preview = " | ".join(self._schema_errors[:2])
            self.app.notify(
                t("ui.llm.error.schema_invalid", preview=preview), severity="error"
            )
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
            self.app.notify(
                t("ui.common.error.validation_failed", preview=preview),
                severity="error",
            )
            return

        try:
            self._write_llm_config_file(sanitized)
            self._load_llm_config()
            if failed_warnings:
                preview = preview_messages(failed_warnings)
                self.app.notify(
                    t("ui.common.warn.saved_with_warning", preview=preview),
                    severity="warning",
                )
            else:
                self.app.notify(t("ui.llm.notify.saved"), severity="information")
        except Exception as e:
            self.app.notify(t("ui.common.error.save_failed", error=e), severity="error")

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
                t("ui.llm.error.config_file_not_found"),
                severity="error",
            )
            return

        test_button = self.query_one("#test-llm-connection", Button)
        test_button.disabled = True

        self.app.notify(t("ui.llm.notify.test_started"))

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
                    t("ui.llm.notify.test_success"),
                    severity="information",
                )
            else:
                self.call_later(
                    self.app.notify,
                    t("ui.llm.warn.test_unexpected", response=response[:50]),
                    severity="warning",
                )
        except Exception as e:
            self.call_later(
                self.app.notify,
                t("ui.llm.error.test_failed", error=e),
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
