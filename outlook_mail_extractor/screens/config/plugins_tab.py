"""Plugins config tab."""

from pathlib import Path
from typing import Any

import yaml
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static, TextArea

from ...i18n import resolve_language, set_language, t
from ...runtime import RuntimeContext, get_runtime_context
from ...ui_schema import (
    load_plugin_ui_schema,
    strip_reserved_metadata,
    validate_ui_schema,
)
from .io_helpers import write_yaml_with_backup
from ..modals.plugin_config_editor import PluginConfigEditorModal


class PluginsConfigTab(Static):
    """Plugin 設定分頁"""

    CSS = """
    #plugin-actions {
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        set_language(resolve_language(self._runtime.paths.config_file))
        self._selected_plugin: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-main"):
            yield Static(t("ui.plugins.title"), id="plugin-list-title")
            yield DataTable(id="plugin-list", show_cursor=True, cursor_type="row")
            with Horizontal(id="plugin-actions"):
                yield Button(
                    t("ui.plugins.button.refresh"),
                    id="refresh-plugins",
                    variant="primary",
                )
                yield Button(
                    t("ui.plugins.button.cleanup"), id="cleanup-plugin-backups"
                )
                yield Button(
                    t("ui.plugins.button.edit"), id="edit-plugin", disabled=True
                )
            yield Static(t("ui.plugins.content.title"), id="plugin-content-title")
            yield TextArea("", id="plugin-content", read_only=True)

    def on_mount(self) -> None:
        self._load_plugins()

    def on_show(self) -> None:
        self._load_plugins()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-plugins":
            self._load_plugins()
            return
        if event.button.id == "cleanup-plugin-backups":
            self._cleanup_plugin_backups()
            return
        if event.button.id == "edit-plugin":
            self._open_plugin_editor()

    def _load_plugins(self) -> None:
        title = self.query_one("#plugin-list-title", Static)
        table = self.query_one("#plugin-list", DataTable)
        edit_button = self.query_one("#edit-plugin", Button)

        table.clear()
        table.add_columns(t("ui.plugins.column.name"), t("ui.common.column.status"))
        self._selected_plugin = None
        edit_button.disabled = True

        plugins_dir = self._runtime.paths.plugins_dir
        if not plugins_dir.exists():
            title.update(t("ui.plugins.title.dir_missing"))
            table.add_row(t("ui.plugins.row.dir_missing"), "")
            return

        plugin_files = sorted(
            [*plugins_dir.glob("*.yaml"), *plugins_dir.glob("*.yaml.sample")]
        )

        if not plugin_files:
            title.update(t("ui.plugins.title.count", count=0))
            table.add_row(t("ui.plugins.row.no_files"), "")
            return

        seen: set[str] = set()
        for pf in plugin_files:
            if pf.name.endswith(".yaml.sample"):
                name = pf.name[:-12]
                is_sample = True
            else:
                name = pf.stem
                is_sample = False
            if name in seen:
                continue
            seen.add(name)
            status = "sample" if is_sample else "active"
            table.add_row(name, status)

        title.update(t("ui.plugins.title.count", count=len(seen)))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#plugin-list", DataTable)
        row = table.get_row_at(event.cursor_row)
        if row:
            plugin_name = row[0]
            self._selected_plugin = str(plugin_name)
            self.query_one("#edit-plugin", Button).disabled = False
            self._load_plugin_content(plugin_name)

    def _load_plugin_content(self, plugin_name: str) -> None:
        content_widget = self.query_one("#plugin-content", TextArea)

        plugins_dir = self._runtime.paths.plugins_dir
        sample_path = plugins_dir / f"{plugin_name}.yaml.sample"
        normal_path = plugins_dir / f"{plugin_name}.yaml"

        file_path = normal_path if normal_path.exists() else sample_path

        if not file_path.exists():
            content_widget.load_text(t("ui.plugins.content.file_missing"))
            return

        try:
            content = file_path.read_text(encoding="utf-8")
            content_widget.load_text(content)
            self.query_one("#plugin-content-title", Static).update(
                t("ui.plugins.content.loaded", plugin=plugin_name)
            )
        except Exception as e:
            content_widget.load_text(t("ui.plugins.content.read_failed", error=e))
            self.query_one("#plugin-content-title", Static).update(
                t("ui.plugins.content.load_error", plugin=plugin_name)
            )

    def _plugin_paths(self, plugin_name: str) -> tuple[Path, Path]:
        plugins_dir = self._runtime.paths.plugins_dir
        sample_path = plugins_dir / f"{plugin_name}.yaml.sample"
        normal_path = plugins_dir / f"{plugin_name}.yaml"
        return sample_path, normal_path

    def _load_plugin_payload(self, plugin_name: str) -> tuple[dict[str, Any], Path]:
        sample_path, normal_path = self._plugin_paths(plugin_name)
        file_path = normal_path if normal_path.exists() else sample_path
        if not file_path.exists():
            raise FileNotFoundError(f"找不到 {plugin_name}.yaml 或 sample")

        try:
            with open(file_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"{file_path.name} YAML 解析錯誤: {e}") from e

        if not isinstance(payload, dict):
            raise ValueError(f"{file_path.name} 內容必須是 YAML 物件")
        return payload, file_path

    def _open_plugin_editor(self) -> None:
        plugin_name = self._selected_plugin
        if not plugin_name:
            self.app.notify(t("ui.plugins.notify.select_first"), severity="warning")
            return

        schema = load_plugin_ui_schema(plugin_name, self._runtime.paths.plugins_dir)
        if not schema:
            self.app.notify(
                t("ui.plugins.notify.schema_missing", plugin=plugin_name),
                severity="warning",
            )
            return

        schema_errors = validate_ui_schema(schema)
        if schema_errors:
            preview = " | ".join(schema_errors[:2])
            self.app.notify(
                t("ui.plugins.error.schema_invalid", preview=preview),
                severity="error",
            )
            return

        try:
            payload, _ = self._load_plugin_payload(plugin_name)
        except Exception as e:
            self.app.notify(str(e), severity="error")
            return

        self.app.push_screen(
            PluginConfigEditorModal(
                plugin_name=plugin_name,
                schema=schema,
                current_config=strip_reserved_metadata(payload),
            ),
            self._handle_plugin_editor_result,
        )

    def _handle_plugin_editor_result(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return

        plugin_name = self._selected_plugin
        if not plugin_name:
            return

        sanitized = strip_reserved_metadata(result)

        try:
            self._write_plugin_config_file(plugin_name, sanitized)
            self._load_plugins()
            self._selected_plugin = plugin_name
            self._load_plugin_content(plugin_name)
            self.query_one("#edit-plugin", Button).disabled = False
            self.app.notify(
                t("ui.plugins.notify.saved", plugin=plugin_name),
                severity="information",
            )
        except Exception as e:
            self.app.notify(t("ui.common.error.save_failed", error=e), severity="error")

    def _write_plugin_config_file(
        self,
        plugin_name: str,
        payload: dict[str, Any],
    ) -> Path:
        """Write plugin config and create `.bak` when original exists."""
        _, normal_path = self._plugin_paths(plugin_name)
        return write_yaml_with_backup(
            normal_path,
            payload,
            backup_path=normal_path.parent / f"{plugin_name}.yaml.bak",
        )

    def _cleanup_backup_files(self) -> tuple[int, list[str]]:
        plugins_dir = self._runtime.paths.plugins_dir
        if not plugins_dir.exists():
            return 0, []

        removed = 0
        failed: list[str] = []
        for backup_path in plugins_dir.glob("*.yaml.bak"):
            try:
                backup_path.unlink()
                removed += 1
            except Exception:
                failed.append(backup_path.name)
        return removed, failed

    def _cleanup_plugin_backups(self) -> None:
        removed, failed = self._cleanup_backup_files()
        self._load_plugins()

        if failed:
            preview = ", ".join(failed[:2])
            if len(failed) > 2:
                preview += t("ui.plugins.cleanup.failed_suffix", count=len(failed))
            self.app.notify(
                t("ui.plugins.cleanup.partial_failed", preview=preview),
                severity="warning",
            )
            return

        self.app.notify(
            t("ui.plugins.cleanup.done", count=removed),
            severity="information",
        )
