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
                base_dir=self._runtime.paths.config_dir,
            ),
            self._handle_plugin_editor_result,
        )

    def _handle_plugin_editor_result(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return

        plugin_name = self._selected_plugin
        if not plugin_name:
            fallback_name = str(result.get("_plugin_name", "")).strip()
            plugin_name = fallback_name or None
        if not plugin_name:
            return

        prompt_profile_renames = self._extract_prompt_profile_renames(result)
        sanitized = strip_reserved_metadata(result)
        inferred_renames = self._infer_prompt_profile_renames(plugin_name, sanitized)
        if inferred_renames:
            merged_renames = dict(inferred_renames)
            merged_renames.update(prompt_profile_renames)
            prompt_profile_renames = merged_renames

        try:
            self._write_plugin_config_file(plugin_name, sanitized)
        except Exception as e:
            self.app.notify(t("ui.common.error.save_failed", error=e), severity="error")
            return

        synced_refs = 0
        if prompt_profile_renames:
            try:
                synced_refs = self._sync_job_prompt_profile_refs(
                    plugin_name, prompt_profile_renames
                )
            except Exception as e:
                self.app.notify(
                    t(
                        "ui.plugins.warn.job_profile_refs_sync_failed",
                        plugin=plugin_name,
                        error=e,
                    ),
                    severity="warning",
                )

        self._load_plugins()
        self._selected_plugin = plugin_name
        self._load_plugin_content(plugin_name)
        self.query_one("#edit-plugin", Button).disabled = False
        self.app.notify(
            t("ui.plugins.notify.saved", plugin=plugin_name),
            severity="information",
        )
        if synced_refs > 0:
            self.app.notify(
                t(
                    "ui.plugins.notify.job_profile_refs_synced",
                    plugin=plugin_name,
                    count=synced_refs,
                ),
                severity="information",
            )

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

    def _extract_prompt_profile_renames(
        self, payload: dict[str, Any]
    ) -> dict[str, str]:
        raw = payload.get("_prompt_profile_renames")
        if not isinstance(raw, dict):
            return {}

        renames: dict[str, str] = {}
        for old, new in raw.items():
            old_key = str(old).strip()
            new_key = str(new).strip()
            if old_key and new_key and old_key != new_key:
                renames[old_key] = new_key

        normalized: dict[str, str] = {}
        for old_key in renames:
            resolved = self._resolve_prompt_profile_rename(old_key, renames)
            if resolved and resolved != old_key:
                normalized[old_key] = resolved
        return normalized

    def _normalize_prompt_profiles(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_profiles = payload.get("prompt_profiles")
        if not isinstance(raw_profiles, dict):
            return {}

        profiles: dict[str, Any] = {}
        for key, value in raw_profiles.items():
            profile_key = str(key).strip()
            if profile_key:
                profiles[profile_key] = value
        return profiles

    def _infer_prompt_profile_renames(
        self,
        plugin_name: str,
        next_payload: dict[str, Any],
    ) -> dict[str, str]:
        try:
            current_payload, _ = self._load_plugin_payload(plugin_name)
        except Exception:
            return {}

        old_profiles = self._normalize_prompt_profiles(current_payload)
        new_profiles = self._normalize_prompt_profiles(next_payload)
        if not old_profiles or not new_profiles:
            return {}

        removed = [key for key in old_profiles if key not in new_profiles]
        added = [key for key in new_profiles if key not in old_profiles]
        if not removed or not added:
            return {}

        renames: dict[str, str] = {}
        remaining_added = list(added)
        for old_key in removed:
            old_value = old_profiles.get(old_key)
            matches = [
                candidate
                for candidate in remaining_added
                if new_profiles.get(candidate) == old_value
            ]
            if len(matches) == 1:
                target = matches[0]
                renames[old_key] = target
                remaining_added.remove(target)

        if renames:
            return renames
        if len(removed) == 1 and len(added) == 1:
            return {removed[0]: added[0]}
        return {}

    def _resolve_prompt_profile_rename(
        self,
        profile_key: str,
        renames: dict[str, str],
    ) -> str:
        current = str(profile_key).strip()
        if not current:
            return ""

        seen = {current}
        while current in renames:
            current = renames[current]
            if current in seen:
                break
            seen.add(current)
        return current

    def _sync_job_prompt_profile_refs(
        self,
        plugin_name: str,
        renames: dict[str, str],
    ) -> int:
        if not renames:
            return 0

        config_path = self._runtime.paths.config_file
        if not config_path.exists():
            return 0

        with open(config_path, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
        if not isinstance(payload, dict):
            raise ValueError("config.yaml content must be an object")

        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            return 0

        updated = 0
        for job in jobs:
            if not isinstance(job, dict):
                continue

            profiles = job.get("plugin_prompt_profiles")
            if not isinstance(profiles, dict):
                continue

            current = profiles.get(plugin_name)
            if not isinstance(current, str):
                continue

            current_key = current.strip()
            if not current_key:
                continue

            resolved = self._resolve_prompt_profile_rename(current_key, renames)
            if resolved and resolved != current_key:
                profiles[plugin_name] = resolved
                updated += 1

        if updated > 0:
            write_yaml_with_backup(
                config_path,
                payload,
                backup_path=config_path.parent / f"{config_path.name}.bak",
            )

        return updated

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
