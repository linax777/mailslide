"""Main config tab."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static

from ...config import load_config, validate_config
from ...i18n import t
from ...plugins import list_plugins
from ...runtime import RuntimeContext, get_runtime_context
from ...ui_schema import (
    build_default_list_item,
    evaluate_rules,
    load_ui_schema,
    schema_text,
    strip_reserved_metadata,
    validate_ui_schema,
)
from ..common import truncate
from ..modals.add_job import AddJobScreen
from ..modals.plugin_config_editor import PluginConfigEditorModal
from .io_helpers import write_yaml_with_backup
from .validation_helpers import collect_rule_failures, preview_messages


MAIN_GENERAL_SETTING_KEYS = ("body_max_length", "llm_mode", "plugin_modules")


class MainConfigTab(Static):
    """一般設定分頁"""

    CSS = """
    #main-config-split {
        height: 100%;
    }
    #main-jobs-pane {
        height: auto;
        min-height: 3;
    }
    #main-jobs-table {
        height: auto;
    }
    #main-schema-pane {
        layout: vertical;
        height: 1fr;
        border-top: solid $accent;
        padding-top: 0;
    }
    #main-schema-actions {
        height: auto;
        min-height: 4;
        margin-bottom: 0;
        padding: 0 0 1 0;
    }
    #main-schema-actions Button {
        height: auto;
        min-height: 3;
    }
    #main-config-title {
        margin-top: 0;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        self._sample_path = self._runtime.paths.config_dir / "config.yaml.sample"
        self._ui_schema = load_ui_schema(self._sample_path)
        self._schema_errors = validate_ui_schema(self._ui_schema)
        self._reset_armed = False
        self._rendered_job_indices: list[int] = []
        self._selected_job_index: int | None = None
        self._is_removing_job = False

    def compose(self) -> ComposeResult:
        with Vertical(id="main-config-split"):
            with Vertical(id="main-jobs-pane"):
                yield Static(t("ui.main.jobs.title"), id="main-jobs-title")
                yield DataTable(
                    id="main-jobs-table",
                    show_cursor=True,
                    cursor_type="row",
                )

            with Vertical(id="main-schema-pane"):
                with Horizontal(id="main-schema-actions"):
                    for button_id in self._visible_button_order():
                        button = self._resolve_button_spec(button_id)
                        if button is None:
                            continue
                        btn = Button(
                            schema_text(
                                button,
                                key_field="label_key",
                                fallback_field="label",
                                default="未命名按鈕",
                            ),
                            id=f"schema-btn-{button_id}",
                            variant=self._resolve_button_variant(
                                str(button.get("variant", "default"))
                            ),
                        )
                        btn.styles.min_height = 5
                        btn.styles.height = "auto"
                        yield btn
                yield Static(t("ui.main.config.title"), id="main-config-title")

    def on_mount(self) -> None:
        actions = self.query_one("#main-schema-actions", Horizontal)
        actions.styles.min_height = 6
        actions.styles.height = "auto"
        self._load_config()

    def _visible_button_order(self) -> tuple[str, ...]:
        return (
            "add_job",
            "edit_job",
            "remove_job",
            "general_settings",
            "reset",
        )

    def _resolve_button_spec(self, button_id: str) -> dict[str, Any] | None:
        buttons = self._ui_schema.get("buttons", [])
        if isinstance(buttons, list):
            for button in buttons:
                if (
                    isinstance(button, dict)
                    and str(button.get("id", "")).strip() == button_id
                ):
                    return button

        if button_id == "general_settings":
            return {
                "id": "general_settings",
                "label": "一般設定",
                "label_key": "ui.main.button.general_settings",
                "variant": "default",
            }
        return None

    def _resolve_button_variant(
        self,
        variant: str,
    ) -> Literal["default", "primary", "success", "warning", "error"]:
        mapping: dict[
            str,
            Literal["default", "primary", "success", "warning", "error"],
        ] = {
            "primary": "primary",
            "success": "success",
            "warning": "warning",
            "error": "error",
            "default": "default",
        }
        return mapping.get(variant, "default")

    def _render_jobs_table(self, config: dict[str, Any]) -> None:
        jobs_pane = self.query_one("#main-jobs-pane", Vertical)
        table = self.query_one("#main-jobs-table", DataTable)
        table.clear(columns=True)
        table.add_columns(
            t("ui.main.table.enabled"),
            t("ui.main.table.name"),
            t("ui.main.table.account"),
            t("ui.main.table.source"),
            t("ui.main.table.destination"),
            t("ui.main.table.plugins"),
            t("ui.main.table.limit"),
        )
        self._rendered_job_indices = []

        jobs = config.get("jobs", [])
        if not isinstance(jobs, list):
            table.styles.height = 4
            jobs_pane.styles.height = 6
            self._selected_job_index = None
            return

        rendered_rows = 0
        for job_index, job in enumerate(jobs):
            if not isinstance(job, dict):
                continue
            plugins = ", ".join(job.get("plugins", [])) or "-"
            enable = "✓" if job.get("enable", True) else "✗"
            table.add_row(
                enable,
                truncate(job.get("name", "")),
                truncate(job.get("account", "")),
                truncate(job.get("source", "")),
                truncate(job.get("destination", "")) or "-",
                truncate(plugins),
                str(job.get("limit", "")),
            )
            self._rendered_job_indices.append(job_index)
            rendered_rows += 1

        if self._selected_job_index not in self._rendered_job_indices:
            self._selected_job_index = None

        visible_rows = max(2, min(rendered_rows + 1, 6))
        table.styles.height = visible_rows
        jobs_pane.styles.height = visible_rows + 2

    def _select_job_row(self, row: int) -> None:
        if row < 0 or row >= len(self._rendered_job_indices):
            self._selected_job_index = None
            return
        self._selected_job_index = self._rendered_job_indices[row]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "main-jobs-table":
            return
        self._select_job_row(int(event.cursor_row))

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        if event.data_table.id != "main-jobs-table":
            return
        self._select_job_row(int(event.coordinate.row))

    def _resolve_remove_job_index(self, jobs: list[Any]) -> int:
        if isinstance(
            self._selected_job_index, int
        ) and 0 <= self._selected_job_index < len(jobs):
            return self._selected_job_index
        return len(jobs) - 1

    def _resolve_edit_job_index(self, jobs: list[Any]) -> int | None:
        if isinstance(
            self._selected_job_index, int
        ) and 0 <= self._selected_job_index < len(jobs):
            return self._selected_job_index
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not event.button.id or not event.button.id.startswith("schema-btn-"):
            return

        action = event.button.id.removeprefix("schema-btn-")
        if action == "add_job":
            self._add_job()
            return
        if action == "edit_job":
            self._edit_job()
            return
        if action == "remove_job":
            self._remove_job(event.button)
            return
        if action == "general_settings":
            self._open_general_settings()
            return
        if action == "reset":
            self._reset_from_sample()
            return

        self.app.notify(
            t("ui.main.notify.button_unhandled", action=action),
            severity="warning",
        )

    def _load_raw_config(self) -> dict[str, Any]:
        config_path = self._runtime.paths.config_file
        if not config_path.exists():
            raise FileNotFoundError(t("ui.main.error.config_missing"))

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError(t("ui.main.error.config_object_required"))
        return data

    def _write_config_file(self, data: dict[str, Any]) -> Path:
        return write_yaml_with_backup(self._runtime.paths.config_file, data)

    def _validate_config_payload(
        self,
        config: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str], list[str]]:
        sanitized = strip_reserved_metadata(config)

        results = evaluate_rules(
            sanitized,
            self._ui_schema.get("validation_rules", []),
        )
        failed_errors, failed_warnings = collect_rule_failures(results)

        try:
            validate_config(sanitized)
        except ValueError as e:
            failed_errors.append(str(e))

        return sanitized, failed_errors, failed_warnings

    def _persist_job_mutation(
        self,
        mutate: Callable[[dict[str, Any]], None],
    ) -> tuple[bool, str | None, list[str]]:
        try:
            config = self._load_raw_config()
            mutate(config)
            sanitized, failed_errors, failed_warnings = self._validate_config_payload(
                config
            )

            if failed_errors:
                preview = preview_messages(failed_errors)
                return (
                    False,
                    t("ui.common.error.validation_failed", preview=preview),
                    [],
                )

            self._write_config_file(sanitized)
            self._load_config()
            self._reset_armed = False
            return True, None, failed_warnings
        except ValueError as e:
            return False, str(e), []
        except Exception as e:
            return False, t("ui.common.error.save_failed", error=e), []

    def _general_settings_schema(self) -> dict[str, Any]:
        fields = self._ui_schema.get("fields", {})
        fields_map = fields if isinstance(fields, dict) else {}
        fallback = self._general_settings_fallback_fields()

        modal_fields: dict[str, Any] = {}
        for key in MAIN_GENERAL_SETTING_KEYS:
            spec = fields_map.get(key)
            if not isinstance(spec, dict):
                spec = fallback[key]
            field_spec = dict(spec)
            if key == "plugin_modules":
                field_spec["type"] = "list[str]"
            modal_fields[key] = field_spec

        return {"fields": modal_fields, "validation_rules": []}

    def _general_settings_fallback_fields(self) -> dict[str, dict[str, Any]]:
        return {
            "body_max_length": {
                "type": "int",
                "label": "Body Max Length",
                "label_key": "ui.main.general.field.body_max_length",
                "required": False,
                "min": 1,
            },
            "llm_mode": {
                "type": "select",
                "label": "LLM Mode",
                "label_key": "ui.main.general.field.llm_mode",
                "required": False,
                "options": ["per_plugin", "share_deprecated"],
            },
            "plugin_modules": {
                "type": "list[str]",
                "label": "Plugin Modules",
                "label_key": "ui.main.general.field.plugin_modules",
                "required": False,
            },
        }

    def _load_general_settings_payload(self) -> dict[str, Any]:
        config = self._load_raw_config()
        return {key: config[key] for key in MAIN_GENERAL_SETTING_KEYS if key in config}

    def _normalize_general_settings_patch(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        normalized: dict[str, Any] = {}

        if "body_max_length" in payload and payload["body_max_length"] is not None:
            normalized["body_max_length"] = int(payload["body_max_length"])

        if "llm_mode" in payload:
            llm_mode = str(payload["llm_mode"]).strip()
            if llm_mode:
                normalized["llm_mode"] = llm_mode

        if "plugin_modules" in payload:
            raw_modules = payload["plugin_modules"]
            if isinstance(raw_modules, list):
                modules = [str(item).strip() for item in raw_modules]
            else:
                modules = [line.strip() for line in str(raw_modules).splitlines()]
            modules = [module for module in modules if module]
            if modules:
                normalized["plugin_modules"] = modules

        return normalized

    def _attempt_save_general_settings(
        self,
        payload: dict[str, Any],
    ) -> tuple[bool, str | None]:
        try:
            config = self._load_raw_config()
            normalized = self._normalize_general_settings_patch(payload)

            for key in MAIN_GENERAL_SETTING_KEYS:
                if key in normalized:
                    config[key] = normalized[key]
                else:
                    config.pop(key, None)

            sanitized, failed_errors, failed_warnings = self._validate_config_payload(
                config
            )
            if failed_errors:
                preview = preview_messages(failed_errors)
                return False, t("ui.common.error.validation_failed", preview=preview)

            self._write_config_file(sanitized)

            refresh_error: Exception | None = None
            try:
                self._load_config()
            except Exception as e:  # pragma: no cover - defensive UI fallback
                refresh_error = e

            self._reset_armed = False
            if failed_warnings:
                self.app.notify(
                    t(
                        "ui.common.warn.saved_with_warning",
                        preview=preview_messages(failed_warnings),
                    ),
                    severity="warning",
                )
            else:
                self.app.notify(
                    t("ui.main.notify.general_saved"),
                    severity="information",
                )

            if refresh_error is not None:
                self.app.notify(
                    t("ui.main.warn.refresh_failed_after_save", error=refresh_error),
                    severity="warning",
                )

            return True, None
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, t("ui.common.error.save_failed", error=e)

    def _open_general_settings(self) -> None:
        if self._schema_errors:
            preview = " | ".join(self._schema_errors[:2])
            self.app.notify(
                t("ui.main.error.schema_invalid", preview=preview),
                severity="error",
            )
            return

        try:
            self.app.push_screen(
                PluginConfigEditorModal(
                    plugin_name=t("ui.main.general.modal_name"),
                    schema=self._general_settings_schema(),
                    current_config=self._load_general_settings_payload(),
                    entity_label=t("ui.main.general.modal_entity"),
                    save_attempt=self._attempt_save_general_settings,
                ),
                lambda _result: None,
            )
        except Exception as e:
            self.app.notify(
                t("ui.main.error.open_general_settings_failed", error=e),
                severity="error",
            )

    def _next_job_name(self, jobs: list[dict[str, Any]]) -> str:
        existing = {str(job.get("name", "")).strip() for job in jobs}
        index = 1
        while True:
            candidate = t("ui.main.default.job_name", index=index)
            if candidate not in existing:
                return candidate
            index += 1

    def _normalize_plugin_ids(self, plugin_ids: list[Any]) -> list[str]:
        normalized: dict[str, str] = {}
        for plugin_id in plugin_ids:
            value = str(plugin_id).strip()
            if not value:
                continue
            normalized.setdefault(value.casefold(), value)
        return [normalized[key] for key in sorted(normalized)]

    def _runtime_plugin_options(self) -> list[str]:
        return self._normalize_plugin_ids(list_plugins())

    def _attempt_add_job_save(
        self,
        result: dict[str, object],
    ) -> tuple[bool, str | None]:
        def mutate(config: dict[str, Any]) -> None:
            jobs = config.get("jobs", [])
            if not isinstance(jobs, list):
                raise ValueError(t("ui.main.error.jobs_must_list"))

            existing_names = {
                str(job.get("name", "")).strip()
                for job in jobs
                if isinstance(job, dict)
            }
            new_name = str(result.get("name", "")).strip()
            if new_name in existing_names:
                raise ValueError(t("ui.main.error.job_name_duplicate", name=new_name))

            jobs.append(dict(result))
            config["jobs"] = jobs

        saved, error, warnings = self._persist_job_mutation(mutate)
        if not saved:
            return False, t("ui.main.error.job_add_failed", error=error)

        if warnings:
            self.app.notify(
                t(
                    "ui.common.warn.saved_with_warning",
                    preview=preview_messages(warnings),
                ),
                severity="warning",
            )
        else:
            self.app.notify(t("ui.main.notify.job_added"), severity="information")
        return True, None

    def _add_job(self) -> None:
        defaults = build_default_list_item(self._ui_schema, "jobs")
        plugin_options = self._runtime_plugin_options()

        try:
            config = self._load_raw_config()
            jobs = config.get("jobs", [])
            if isinstance(jobs, list) and jobs:
                if not str(defaults.get("name", "")).strip():
                    defaults["name"] = self._next_job_name(
                        [job for job in jobs if isinstance(job, dict)]
                    )
        except Exception:
            defaults.setdefault("name", t("ui.main.default.job_name", index=1))

        self.app.push_screen(
            AddJobScreen(
                plugin_options=plugin_options,
                defaults=defaults,
                save_attempt=self._attempt_add_job_save,
            ),
            lambda _result: None,
        )

    def _attempt_edit_job_save(
        self,
        edit_index: int,
        result: dict[str, object],
    ) -> tuple[bool, str | None]:
        def mutate(config: dict[str, Any]) -> None:
            jobs = config.get("jobs", [])
            if not isinstance(jobs, list):
                raise ValueError(t("ui.main.error.jobs_must_list"))
            if not (0 <= edit_index < len(jobs)):
                raise ValueError(t("ui.main.error.job_not_found"))

            updated_name = str(result.get("name", "")).strip()
            for idx, job in enumerate(jobs):
                if idx == edit_index or not isinstance(job, dict):
                    continue
                if str(job.get("name", "")).strip() == updated_name:
                    raise ValueError(
                        t("ui.main.error.job_name_duplicate", name=updated_name)
                    )

            jobs[edit_index] = dict(result)
            config["jobs"] = jobs

        saved, error, warnings = self._persist_job_mutation(mutate)
        if not saved:
            return False, t("ui.main.error.job_edit_failed", error=error)

        self._selected_job_index = edit_index
        if warnings:
            self.app.notify(
                t(
                    "ui.common.warn.saved_with_warning",
                    preview=preview_messages(warnings),
                ),
                severity="warning",
            )
        else:
            self.app.notify(
                t("ui.main.notify.job_updated", index=edit_index + 1),
                severity="information",
            )
        return True, None

    def _edit_job(self) -> None:
        try:
            config = self._load_raw_config()
            jobs = config.get("jobs", [])
            if not isinstance(jobs, list):
                raise ValueError(t("ui.main.error.jobs_must_list"))
            if not jobs:
                self.app.notify(t("ui.main.warn.no_job_to_edit"), severity="warning")
                return

            edit_index = self._resolve_edit_job_index(jobs)
            if edit_index is None:
                self.app.notify(
                    t("ui.main.warn.select_job_to_edit"),
                    severity="warning",
                )
                return

            selected_job = jobs[edit_index]
            if not isinstance(selected_job, dict):
                raise ValueError(t("ui.main.error.selected_job_invalid"))

            defaults = dict(selected_job)
            available_plugins = self._runtime_plugin_options()
            raw_existing_plugins = defaults.get("plugins", [])
            existing_plugins = self._normalize_plugin_ids(
                raw_existing_plugins if isinstance(raw_existing_plugins, list) else []
            )
            available_plugin_keys = {plugin.casefold() for plugin in available_plugins}
            unavailable_plugins = [
                plugin
                for plugin in existing_plugins
                if plugin.casefold() not in available_plugin_keys
            ]
            plugin_options = [*available_plugins, *unavailable_plugins]

            self.app.push_screen(
                AddJobScreen(
                    plugin_options=plugin_options,
                    unavailable_plugins=unavailable_plugins,
                    defaults=defaults,
                    title=t("ui.main.edit_modal.title", index=edit_index + 1),
                    save_button_label=t("ui.main.edit_modal.save"),
                    save_attempt=lambda result: self._attempt_edit_job_save(
                        edit_index,
                        result,
                    ),
                ),
                lambda _result: None,
            )
        except Exception as e:
            self.app.notify(
                t("ui.main.error.open_edit_failed", error=e),
                severity="error",
            )

    def _remove_job(self, trigger_button: Button | None = None) -> None:
        if self._is_removing_job:
            return

        try:
            config = self._load_raw_config()
            jobs = config.get("jobs", [])
            if not isinstance(jobs, list):
                raise ValueError(t("ui.main.error.jobs_must_list"))
            if not jobs:
                self.app.notify(t("ui.main.warn.no_job_to_remove"), severity="warning")
                return

            remove_index = self._resolve_remove_job_index(jobs)
            removed = jobs[remove_index]

            self._is_removing_job = True
            if trigger_button is not None:
                trigger_button.disabled = True

            def mutate(payload: dict[str, Any]) -> None:
                mutable_jobs = payload.get("jobs", [])
                if not isinstance(mutable_jobs, list):
                    raise ValueError(t("ui.main.error.jobs_must_list"))
                if not (0 <= remove_index < len(mutable_jobs)):
                    raise ValueError(t("ui.main.error.job_not_found"))
                mutable_jobs.pop(remove_index)
                payload["jobs"] = mutable_jobs

            saved, error, warnings = self._persist_job_mutation(mutate)
            if not saved:
                raise ValueError(error)

            if warnings:
                self.app.notify(
                    t(
                        "ui.common.warn.saved_with_warning",
                        preview=preview_messages(warnings),
                    ),
                    severity="warning",
                )
            else:
                name = (
                    str(removed.get("name", t("ui.main.default.unnamed")))
                    if isinstance(removed, dict)
                    else t("ui.main.default.unknown")
                )
                self.app.notify(
                    t("ui.main.notify.job_removed", index=remove_index + 1, name=name),
                    severity="information",
                )
        except Exception as e:
            self.app.notify(
                t("ui.main.error.job_remove_failed", error=e),
                severity="error",
            )
        finally:
            self._is_removing_job = False
            if trigger_button is not None:
                trigger_button.disabled = False

    def _reset_from_sample(self) -> None:
        if not self._reset_armed:
            self._reset_armed = True
            self.app.notify(
                t("ui.main.warn.reset_confirm"),
                severity="warning",
            )
            return

        try:
            with open(self._sample_path, encoding="utf-8") as f:
                sample = yaml.safe_load(f) or {}
            if not isinstance(sample, dict):
                raise ValueError(t("ui.main.error.sample_invalid"))

            sanitized = strip_reserved_metadata(sample)
            self._write_config_file(sanitized)
            self._load_config()
            self.app.notify(t("ui.main.notify.reset_done"), severity="information")
        except Exception as e:
            self.app.notify(t("ui.main.error.reset_failed", error=e), severity="error")
        finally:
            self._reset_armed = False

    def _load_config(self) -> None:
        table = self.query_one("#main-jobs-table", DataTable)
        table.clear(columns=True)

        config_path = self._runtime.paths.config_file
        if not config_path.exists():
            self._render_jobs_table({"jobs": []})
            self.query_one("#main-config-title", Static).update(
                t("ui.main.config.title.not_initialized")
            )
            return

        try:
            config = load_config(config_path)
            self._render_jobs_table(config)
            self.query_one("#main-config-title", Static).update(
                t("ui.main.config.title.ok")
            )
        except Exception as e:
            self._render_jobs_table({"jobs": []})
            self.query_one("#main-config-title", Static).update(
                t("ui.main.config.title.error", error=e)
            )
