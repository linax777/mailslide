"""Schema-driven plugin config editor modal."""

import json
import re
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    OptionList,
    SelectionList,
    Static,
    Switch,
    TextArea,
)

from ...i18n import t
from ...ui_schema import evaluate_rules, schema_text


class PluginConfigEditorModal(ModalScreen[dict[str, Any] | None]):
    """Schema-driven plugin config editor modal."""

    CSS = """
    PluginConfigEditorModal {
        align: center middle;
    }
    #plugin-editor-dialog {
        width: 92;
        max-width: 120;
        height: 90%;
        min-height: 24;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #plugin-editor-form {
        height: 1fr;
        min-height: 8;
        margin-bottom: 1;
    }
    .plugin-field-label {
        margin-top: 1;
    }
    #plugin-editor-error {
        color: $error;
        min-height: 2;
    }
    #plugin-editor-actions {
        height: auto;
        margin-top: 1;
    }
    .plugin-select-field {
        height: 6;
    }
    .plugin-textarea-field {
        height: 7;
    }
    #plugin-prompt-profiles-row {
        height: auto;
        min-height: 14;
        margin-top: 1;
    }
    #plugin-prompt-profile-list-wrap {
        width: 28;
        min-width: 22;
    }
    #plugin-prompt-profile-list {
        height: 1fr;
        min-height: 10;
    }
    #plugin-prompt-profile-actions {
        height: auto;
        margin-top: 1;
    }
    #plugin-prompt-profile-detail {
        width: 1fr;
    }
    #plugin-prompt-system_prompt {
        height: 10;
    }
    """

    def __init__(
        self,
        plugin_name: str,
        schema: dict[str, Any],
        current_config: dict[str, Any],
        entity_label: str = "Plugin",
        base_dir: Path | None = None,
    ):
        super().__init__()
        self._plugin_name = plugin_name
        self._entity_label = entity_label
        self._base_dir = Path(base_dir) if base_dir is not None else None
        fields = schema.get("fields", {})
        self._fields = fields if isinstance(fields, dict) else {}
        buttons = schema.get("buttons", [])
        self._buttons = buttons if isinstance(buttons, list) else []
        rules = schema.get("validation_rules", [])
        self._rules = rules if isinstance(rules, list) else []
        self._current = current_config
        self._json_format_raw = self._extract_json_format_raw(current_config)
        self._json_format_examples, self._json_unparsed_keys = (
            self._parse_json_format_examples(self._json_format_raw)
        )
        self._use_prompt_profile_editor = self._has_prompt_profiles_field()
        self._prompt_profiles_state = self._init_prompt_profiles_state()
        self._prompt_profile_order = list(self._prompt_profiles_state.keys())
        self._active_prompt_profile = (
            self._prompt_profile_order[0] if self._prompt_profile_order else ""
        )
        self._prompt_profile_renames: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-editor-dialog"):
            yield Static(
                t(
                    "ui.plugin_editor.title",
                    entity=self._entity_label,
                    name=self._plugin_name,
                ),
                id="plugin-editor-title",
            )
            with VerticalScroll(id="plugin-editor-form"):
                yield from self._compose_dynamic_fields()
                yield from self._compose_json_format_editor()

            yield Static("", id="plugin-editor-error")
            with Horizontal(id="plugin-editor-actions"):
                yield Button(
                    t("ui.plugin_editor.button.cancel"), id="plugin-editor-cancel"
                )
                actions = self._schema_actions()
                if "validate" in actions:
                    yield Button(
                        t("ui.plugin_editor.button.validate"),
                        id="plugin-editor-validate",
                        variant="warning",
                    )
                if "save" in actions:
                    yield Button(
                        t("ui.plugin_editor.button.save"),
                        id="plugin-editor-save",
                        variant="primary",
                    )

    def on_mount(self) -> None:
        first_field = next(iter(self._fields.keys()), None)
        if first_field is None:
            return

        widget_id = self._widget_id(first_field)
        try:
            self.query_one(f"#{widget_id}").focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "plugin-editor-cancel":
            self.dismiss(None)
            return

        if event.button.id == "plugin-prompt-add":
            self._add_prompt_profile()
            return

        if event.button.id == "plugin-prompt-remove":
            self._remove_active_prompt_profile()
            return

        try:
            payload = self._collect_payload()
        except ValueError as e:
            self._show_error(str(e))
            return

        has_error, has_warning, preview = self._evaluate_rule_result(payload)
        if event.button.id == "plugin-editor-validate":
            if has_error:
                self.app.notify(
                    t("ui.common.error.validation_failed", preview=preview),
                    severity="error",
                )
            elif has_warning:
                self.app.notify(
                    t("ui.plugin_editor.warn.validation_done", preview=preview),
                    severity="warning",
                )
            else:
                self.app.notify(
                    t("ui.plugin_editor.notify.validation_passed"),
                    severity="information",
                )
            return

        if event.button.id == "plugin-editor-save":
            if has_error:
                self._show_error(preview)
                return
            if has_warning:
                self.app.notify(
                    t("ui.common.warn.saved_with_warning", preview=preview),
                    severity="warning",
                )
            self.dismiss(payload)

    def _add_prompt_profile(self) -> None:
        if not self._use_prompt_profile_editor:
            return

        self._save_active_prompt_profile_fields()
        base_name = "new_profile"
        index = 1
        while f"{base_name}_{index}" in self._prompt_profiles_state:
            index += 1
        key = f"{base_name}_{index}"

        self._prompt_profiles_state[key] = {
            "version": 1,
            "description": "",
            "system_prompt": "",
        }
        self._prompt_profile_order.append(key)
        self._active_prompt_profile = key
        self._refresh_prompt_profile_list()
        self._load_active_prompt_profile_fields()

    def _remove_active_prompt_profile(self) -> None:
        if not self._use_prompt_profile_editor:
            return
        if len(self._prompt_profile_order) <= 1:
            self.app.notify(
                t("ui.plugin_editor.warn.keep_one_profile"), severity="warning"
            )
            return

        key = self._active_prompt_profile
        if key not in self._prompt_profiles_state:
            return

        del self._prompt_profiles_state[key]
        self._prompt_profile_order = [
            item for item in self._prompt_profile_order if item != key
        ]
        self._active_prompt_profile = self._prompt_profile_order[0]
        self._refresh_prompt_profile_list()
        self._load_active_prompt_profile_fields()

    def _refresh_prompt_profile_list(self) -> None:
        option_list = self.query_one("#plugin-prompt-profile-list", OptionList)
        option_list.clear_options()
        option_list.add_options(self._prompt_profile_order)
        try:
            option_list.highlighted = self._prompt_profile_order.index(
                self._active_prompt_profile
            )
        except ValueError:
            option_list.highlighted = 0

    def _widget_id(self, field_name: str) -> str:
        return f"plugin-field-{field_name}"

    def _compose_dynamic_fields(self) -> ComposeResult:
        for field_name, spec in self._fields.items():
            if not isinstance(spec, dict):
                continue

            if self._is_prompt_profiles_field(field_name, spec):
                yield from self._compose_prompt_profile_editor(field_name, spec)
                continue

            required = bool(spec.get("required", False))
            marker = " *" if required else ""
            label = schema_text(
                spec,
                key_field="label_key",
                fallback_field="label",
                default=field_name,
            )
            yield Static(f"{label}{marker}", classes="plugin-field-label")
            yield self._build_field_widget(field_name, spec)

    def _compose_prompt_profile_editor(
        self,
        field_name: str,
        spec: dict[str, Any],
    ) -> ComposeResult:
        required = bool(spec.get("required", False))
        marker = " *" if required else ""
        label = schema_text(
            spec,
            key_field="label_key",
            fallback_field="label",
            default=field_name,
        )
        yield Static(f"{label}{marker}", classes="plugin-field-label")

        with Horizontal(id="plugin-prompt-profiles-row"):
            with Vertical(id="plugin-prompt-profile-list-wrap"):
                options = self._prompt_profile_order or ["(無 profile)"]
                yield OptionList(*options, id="plugin-prompt-profile-list")
                with Horizontal(id="plugin-prompt-profile-actions"):
                    yield Button(
                        t("ui.plugin_editor.button.add_profile"),
                        id="plugin-prompt-add",
                        variant="success",
                    )
                    yield Button(
                        t("ui.plugin_editor.button.remove_profile"),
                        id="plugin-prompt-remove",
                        variant="warning",
                    )

            with Vertical(id="plugin-prompt-profile-detail"):
                yield Static(
                    t("ui.plugin_editor.field.profile_key"),
                    classes="plugin-field-label",
                )
                yield Input(
                    self._active_prompt_profile,
                    id="plugin-prompt-key",
                )
                yield Static(
                    t("ui.plugin_editor.field.version"), classes="plugin-field-label"
                )
                yield Input(
                    self._prompt_profile_value(self._active_prompt_profile, "version"),
                    id="plugin-prompt-version",
                )
                yield Static(
                    t("ui.plugin_editor.field.description"),
                    classes="plugin-field-label",
                )
                yield Input(
                    self._prompt_profile_value(
                        self._active_prompt_profile, "description"
                    ),
                    id="plugin-prompt-description",
                )
                yield Static(
                    t("ui.plugin_editor.field.system_prompt"),
                    classes="plugin-field-label",
                )
                yield TextArea(
                    self._prompt_profile_value(
                        self._active_prompt_profile, "system_prompt"
                    ),
                    id="plugin-prompt-system_prompt",
                    classes="plugin-textarea-field",
                )

    def _build_field_widget(self, field_name: str, spec: dict[str, Any]) -> Any:
        field_type = str(spec.get("type", "str")).lower()
        widget_id = self._widget_id(field_name)

        if field_type == "bool":
            return Switch(
                value=self._resolve_initial_bool(field_name, spec),
                id=widget_id,
            )

        if field_type in {"select", "multiselect"}:
            options = self._options(spec)
            selected = self._resolve_initial_selection(field_name, spec)
            return SelectionList(
                *[
                    (
                        option,
                        option,
                        option in selected,
                    )
                    for option in options
                ],
                id=widget_id,
                classes="plugin-select-field",
            )

        if field_type in {"textarea", "yaml", "list[str]", "list"}:
            rows = spec.get("rows", 7)
            try:
                rows_value = int(rows)
            except Exception:
                rows_value = 7
            textarea = TextArea(
                self._resolve_initial_text(field_name, spec),
                id=widget_id,
                classes="plugin-textarea-field",
            )
            textarea.styles.height = max(4, min(rows_value + 1, 12))
            return textarea

        if field_type == "secret":
            return Input(
                self._resolve_initial_text(field_name, spec),
                placeholder=str(spec.get("placeholder", "")),
                password=True,
                id=widget_id,
            )

        return Input(
            self._resolve_initial_text(field_name, spec),
            placeholder=str(spec.get("placeholder", "")),
            id=widget_id,
        )

    def _compose_json_format_editor(self) -> ComposeResult:
        if not self._json_format_examples and not self._json_unparsed_keys:
            return

        yield Static(
            t("ui.plugin_editor.json.title"),
            classes="plugin-field-label",
        )

        for key, template in self._json_format_examples.items():
            yield Static(f"{key}", classes="plugin-field-label")
            for field_name, field_value in template.items():
                locked = self._is_locked_json_field(field_name)
                lock_suffix = t("ui.plugin_editor.json.locked_suffix") if locked else ""
                yield Static(
                    f"{field_name}{lock_suffix}",
                    classes="plugin-field-label",
                )

                if locked:
                    yield Static(str(field_value))
                    continue

                yield self._build_json_format_widget(key, field_name, field_value)

        if self._json_unparsed_keys:
            names = ", ".join(self._json_unparsed_keys)
            yield Static(
                t("ui.plugin_editor.json.unparsed", names=names),
                classes="plugin-field-label",
            )

    def _build_json_format_widget(self, key: str, field_name: str, value: Any) -> Any:
        widget_id = self._json_field_widget_id(key, field_name)
        if isinstance(value, bool):
            return Switch(value=value, id=widget_id)
        if isinstance(value, list):
            textarea = TextArea(
                "\n".join(str(item) for item in value),
                id=widget_id,
                classes="plugin-textarea-field",
            )
            textarea.styles.height = 5
            return textarea
        return Input(str(value), id=widget_id)

    def _json_widget_id(self, key: str) -> str:
        safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
        return f"plugin-jsonfmt-{safe_key}"

    def _json_field_widget_id(self, key: str, field_name: str) -> str:
        safe_field = re.sub(r"[^a-zA-Z0-9_-]", "_", field_name)
        return f"{self._json_widget_id(key)}-{safe_field}"

    def _is_locked_json_field(self, field_name: str) -> bool:
        return field_name in {"action", "start", "end"}

    def _extract_json_format_raw(self, config: dict[str, Any]) -> dict[str, str]:
        json_format = config.get("response_json_format")
        if not isinstance(json_format, dict):
            return {}
        return {str(key): str(value) for key, value in json_format.items()}

    def _parse_json_format_examples(
        self,
        raw: dict[str, str],
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        parsed: dict[str, dict[str, Any]] = {}
        unparsed: list[str] = []
        for key, value in raw.items():
            try:
                payload = json.loads(value)
            except json.JSONDecodeError:
                unparsed.append(key)
                continue
            if not isinstance(payload, dict):
                unparsed.append(key)
                continue
            parsed[key] = payload
        return parsed, unparsed

    def _schema_actions(self) -> set[str]:
        actions: set[str] = set()
        for button in self._buttons:
            if not isinstance(button, dict):
                continue
            action = str(button.get("action", "")).strip().lower()
            if action:
                actions.add(action)
        if not actions:
            return {"validate", "save"}
        return actions

    def _show_error(self, message: str) -> None:
        self.query_one("#plugin-editor-error", Static).update(message)

    def _options(self, spec: dict[str, Any]) -> list[str]:
        options = spec.get("options", [])
        if not isinstance(options, list):
            return []
        return [str(option) for option in options]

    def _resolve_default(self, field_name: str, spec: dict[str, Any]) -> Any:
        if field_name in self._current:
            return self._current[field_name]
        if "default" in spec:
            return spec["default"]

        field_type = str(spec.get("type", "str")).lower()
        if field_type == "bool":
            return False
        if field_type in {"int", "number"}:
            return 0
        if field_type in {"multiselect", "list", "list[str]"}:
            return []
        return ""

    def _resolve_initial_bool(self, field_name: str, spec: dict[str, Any]) -> bool:
        value = self._resolve_default(field_name, spec)
        return value if isinstance(value, bool) else bool(value)

    def _resolve_initial_text(self, field_name: str, spec: dict[str, Any]) -> str:
        value = self._resolve_default(field_name, spec)
        field_type = str(spec.get("type", "str")).lower()
        if field_type == "path":
            return self._resolve_initial_path(value)
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        if value is None:
            return ""
        return str(value)

    def _resolve_initial_path(self, value: Any) -> str:
        if value is None:
            return ""

        raw = str(value).strip()
        if not raw:
            return ""

        # Keep env-var style paths unchanged to avoid breaking intent.
        if re.search(r"\$\{[^}]+\}|%[^%]+%", raw):
            return raw

        candidate = Path(raw).expanduser()
        if candidate.is_absolute() or self._base_dir is None:
            return str(candidate)

        return str((self._base_dir / candidate).resolve())

    def _resolve_initial_selection(
        self,
        field_name: str,
        spec: dict[str, Any],
    ) -> set[str]:
        value = self._resolve_default(field_name, spec)
        field_type = str(spec.get("type", "select")).lower()
        options = set(self._options(spec))
        if field_type == "multiselect":
            if not isinstance(value, list):
                return set()
            return {str(item) for item in value if str(item) in options}

        selected = str(value) if value is not None else ""
        return {selected} if selected in options else set()

    def _collect_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field_name, spec in self._fields.items():
            if not isinstance(spec, dict):
                continue

            field_type = str(spec.get("type", "str")).lower()
            field_label = schema_text(
                spec,
                key_field="label_key",
                fallback_field="label",
                default=field_name,
            )
            value = self._collect_field_value(field_name, spec, field_type, field_label)
            self._validate_field_value(spec, field_type, field_label, value)

            if value is not None:
                payload[field_name] = value

        response_json_format = self._collect_response_json_format()
        if response_json_format:
            payload["response_json_format"] = response_json_format

        self._apply_prompt_profile_renames(payload)

        return payload

    def _collect_field_value(
        self,
        field_name: str,
        spec: dict[str, Any],
        field_type: str,
        field_label: str,
    ) -> Any:
        widget_id = f"#{self._widget_id(field_name)}"
        options = self._options(spec)

        if self._is_prompt_profiles_field(field_name, spec):
            try:
                return self._collect_prompt_profiles_from_editor()
            except ValueError:
                raise
            except Exception:
                pass

        if field_type == "bool":
            return self.query_one(widget_id, Switch).value

        if field_type in {"select", "multiselect"}:
            selector = self.query_one(widget_id, SelectionList)
            selected = [
                option for option in options if option in set(selector.selected)
            ]
            if field_type == "select":
                if len(selected) > 1:
                    raise ValueError(
                        t("ui.plugin_editor.error.select_one", label=field_label)
                    )
                return selected[0] if selected else ""
            return selected

        if field_type == "textarea":
            return str(self.query_one(widget_id, TextArea).text).strip()

        if field_type == "yaml":
            import yaml

            raw = str(self.query_one(widget_id, TextArea).text).strip()
            if not raw:
                return None
            try:
                return yaml.safe_load(raw)
            except yaml.YAMLError as exc:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.invalid_yaml",
                        label=field_label,
                        error=exc,
                    )
                ) from exc

        if field_type in {"str", "path", "secret"}:
            return self.query_one(widget_id, Input).value.strip()

        if field_type in {"list", "list[str]"}:
            lines = [
                line.strip()
                for line in self.query_one(widget_id, TextArea).text.splitlines()
            ]
            return [line for line in lines if line]

        if field_type in {"int", "number"}:
            text = self.query_one(widget_id, Input).value.strip()
            if not text:
                return None
            try:
                return int(text)
            except ValueError as exc:
                raise ValueError(
                    t("ui.plugin_editor.error.int_required", label=field_label)
                ) from exc

        return self.query_one(widget_id, Input).value.strip()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "plugin-prompt-profile-list":
            return

        try:
            self._save_active_prompt_profile_fields()
        except ValueError as exc:
            self._show_error(str(exc))
            self._refresh_prompt_profile_list()
            return

        if event.option_index < 0 or event.option_index >= len(
            self._prompt_profile_order
        ):
            return
        self._active_prompt_profile = self._prompt_profile_order[event.option_index]
        self._load_active_prompt_profile_fields()

    def _has_prompt_profiles_field(self) -> bool:
        for field_name, spec in self._fields.items():
            if self._is_prompt_profiles_field(field_name, spec):
                return True
        return False

    def _is_prompt_profiles_field(self, field_name: str, spec: dict[str, Any]) -> bool:
        return (
            field_name == "prompt_profiles"
            and str(spec.get("type", "")).lower() == "yaml"
        )

    def _init_prompt_profiles_state(self) -> dict[str, dict[str, Any]]:
        if not self._use_prompt_profile_editor:
            return {}

        raw_profiles = self._current.get("prompt_profiles", {})
        parsed: dict[str, dict[str, Any]] = {}
        if isinstance(raw_profiles, dict):
            for key, value in raw_profiles.items():
                profile_key = str(key)
                if isinstance(value, dict):
                    parsed[profile_key] = {
                        "version": value.get("version", 1),
                        "description": str(value.get("description", "")),
                        "system_prompt": str(value.get("system_prompt", "")),
                    }
                else:
                    parsed[profile_key] = {
                        "version": 1,
                        "description": "",
                        "system_prompt": str(value),
                    }

        if parsed:
            return parsed

        fallback_prompt = str(self._current.get("system_prompt", "")).strip()
        return {
            "default_v1": {
                "version": 1,
                "description": "",
                "system_prompt": fallback_prompt,
            }
        }

    def _prompt_profile_value(self, key: str, field: str) -> str:
        profile = self._prompt_profiles_state.get(key, {})
        value = profile.get(field, "")
        return "" if value is None else str(value)

    def _record_prompt_profile_rename(self, old_key: str, new_key: str) -> None:
        if old_key == new_key:
            return

        rewrites: dict[str, str] = {}
        for source, target in self._prompt_profile_renames.items():
            rewrites[source] = new_key if target == old_key else target
        rewrites[old_key] = new_key

        for source in list(rewrites.keys()):
            seen = {source}
            target = rewrites[source]
            while target in rewrites and target not in seen:
                seen.add(target)
                target = rewrites[target]
            rewrites[source] = target

        self._prompt_profile_renames = {
            source: target
            for source, target in rewrites.items()
            if source and target and source != target
        }

    def _resolve_prompt_profile_rename(self, profile_key: str) -> str:
        current = str(profile_key).strip()
        if not current:
            return ""

        seen = {current}
        while current in self._prompt_profile_renames:
            current = self._prompt_profile_renames[current]
            if current in seen:
                break
            seen.add(current)
        return current

    def _save_active_prompt_profile_fields(self) -> None:
        key = self._active_prompt_profile
        if not key or key not in self._prompt_profiles_state:
            return

        typed_key = self.query_one("#plugin-prompt-key", Input).value.strip()
        if not typed_key:
            raise ValueError(t("ui.plugin_editor.error.profile_key_required"))
        if typed_key != key:
            if typed_key in self._prompt_profiles_state:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.profile_key_duplicate",
                        profile_key=typed_key,
                    )
                )
            profile_payload = self._prompt_profiles_state.pop(key)
            self._prompt_profiles_state[typed_key] = profile_payload
            try:
                index = self._prompt_profile_order.index(key)
                self._prompt_profile_order[index] = typed_key
            except ValueError:
                self._prompt_profile_order.append(typed_key)
            self._active_prompt_profile = typed_key
            self._record_prompt_profile_rename(key, typed_key)
            try:
                self._refresh_prompt_profile_list()
            except Exception:
                pass
            key = typed_key

        version_text = self.query_one("#plugin-prompt-version", Input).value.strip()
        version = 1
        if version_text:
            try:
                version = int(version_text)
            except ValueError:
                version = 1

        self._prompt_profiles_state[key] = {
            "version": version,
            "description": self.query_one(
                "#plugin-prompt-description", Input
            ).value.strip(),
            "system_prompt": str(
                self.query_one("#plugin-prompt-system_prompt", TextArea).text
            ).strip(),
        }

    def _load_active_prompt_profile_fields(self) -> None:
        key = self._active_prompt_profile
        profile = self._prompt_profiles_state.get(key, {})
        self.query_one("#plugin-prompt-key", Input).value = key
        self.query_one("#plugin-prompt-version", Input).value = str(
            profile.get("version", 1)
        )
        self.query_one("#plugin-prompt-description", Input).value = str(
            profile.get("description", "")
        )
        self.query_one("#plugin-prompt-system_prompt", TextArea).load_text(
            str(profile.get("system_prompt", ""))
        )

    def _collect_prompt_profiles_from_editor(self) -> dict[str, dict[str, Any]]:
        self._save_active_prompt_profile_fields()
        payload: dict[str, dict[str, Any]] = {}
        for key in self._prompt_profile_order:
            profile = self._prompt_profiles_state.get(key, {})
            payload[key] = {
                "version": int(profile.get("version", 1) or 1),
                "description": str(profile.get("description", "")).strip(),
                "system_prompt": str(profile.get("system_prompt", "")).strip(),
            }
        return payload

    def _apply_prompt_profile_renames(self, payload: dict[str, Any]) -> None:
        if not self._prompt_profile_renames:
            return

        default_profile = payload.get("default_prompt_profile")
        if isinstance(default_profile, str):
            resolved = self._resolve_prompt_profile_rename(default_profile)
            if resolved:
                payload["default_prompt_profile"] = resolved

        payload["_plugin_name"] = self._plugin_name
        payload["_prompt_profile_renames"] = dict(self._prompt_profile_renames)

    def _validate_field_value(
        self,
        spec: dict[str, Any],
        field_type: str,
        field_label: str,
        value: Any,
    ) -> None:
        required = bool(spec.get("required", False))
        options = self._options(spec)

        if required and (value is None or value == "" or value == []):
            raise ValueError(t("ui.plugin_editor.error.required", label=field_label))

        if field_type == "select" and value and value not in options:
            raise ValueError(
                t("ui.plugin_editor.error.select_invalid", label=field_label)
            )

        if field_type == "multiselect" and isinstance(value, list):
            illegal = [item for item in value if item not in options]
            if illegal:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.multiselect_invalid",
                        label=field_label,
                        illegal=", ".join(illegal),
                    )
                )

        int_value = (
            value if isinstance(value, int) and not isinstance(value, bool) else None
        )
        if field_type in {"int", "number"} and int_value is not None:
            minimum = spec.get("min")
            maximum = spec.get("max")
            if isinstance(minimum, int) and int_value < minimum:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.min_value",
                        label=field_label,
                        minimum=minimum,
                    )
                )
            if isinstance(maximum, int) and int_value > maximum:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.max_value",
                        label=field_label,
                        maximum=maximum,
                    )
                )

    def _collect_response_json_format(self) -> dict[str, str]:
        if not self._json_format_raw:
            return {}

        response_json_format = dict(self._json_format_raw)
        for key, template in self._json_format_examples.items():
            rebuilt: dict[str, Any] = {}
            for field_name, original_value in template.items():
                if self._is_locked_json_field(field_name):
                    rebuilt[field_name] = original_value
                    continue
                rebuilt[field_name] = self._read_json_template_value(
                    key,
                    field_name,
                    original_value,
                )

            response_json_format[key] = json.dumps(rebuilt, ensure_ascii=False)
        return response_json_format

    def _read_json_template_value(
        self, key: str, field_name: str, original_value: Any
    ) -> Any:
        widget_id = f"#{self._json_field_widget_id(key, field_name)}"
        if isinstance(original_value, bool):
            return bool(self.query_one(widget_id, Switch).value)
        if isinstance(original_value, list):
            lines = [
                line.strip()
                for line in self.query_one(widget_id, TextArea).text.splitlines()
            ]
            return [line for line in lines if line]
        if isinstance(original_value, int) and not isinstance(original_value, bool):
            text = self.query_one(widget_id, Input).value.strip()
            if not text:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.template_int_required",
                        template_key=key,
                        field=field_name,
                    )
                )
            try:
                return int(text)
            except ValueError as exc:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.template_int_required",
                        template_key=key,
                        field=field_name,
                    )
                ) from exc
        if isinstance(original_value, float):
            text = self.query_one(widget_id, Input).value.strip()
            if not text:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.template_number_required",
                        template_key=key,
                        field=field_name,
                    )
                )
            try:
                return float(text)
            except ValueError as exc:
                raise ValueError(
                    t(
                        "ui.plugin_editor.error.template_number_required",
                        template_key=key,
                        field=field_name,
                    )
                ) from exc
        return self.query_one(widget_id, Input).value.strip()

    def _evaluate_rule_result(self, payload: dict[str, Any]) -> tuple[bool, bool, str]:
        results = evaluate_rules(payload, self._rules)
        failed_errors: list[str] = []
        failed_warnings: list[str] = []
        for result in results:
            if result.passed:
                continue
            if result.level == "error":
                failed_errors.append(result.message)
            else:
                failed_warnings.append(result.message)

        if failed_errors:
            return True, bool(failed_warnings), "；".join(failed_errors[:2])
        if failed_warnings:
            return False, True, "；".join(failed_warnings[:2])
        return False, False, ""
