"""Schema-driven plugin config editor modal."""

import json
import re
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, SelectionList, Static, Switch, TextArea

from ...ui_schema import evaluate_rules


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
    """

    def __init__(
        self,
        plugin_name: str,
        schema: dict[str, Any],
        current_config: dict[str, Any],
        entity_label: str = "Plugin",
    ):
        super().__init__()
        self._plugin_name = plugin_name
        self._entity_label = entity_label
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

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-editor-dialog"):
            yield Static(
                f"🧩 編輯 {self._entity_label}: {self._plugin_name}",
                id="plugin-editor-title",
            )
            with VerticalScroll(id="plugin-editor-form"):
                yield from self._compose_dynamic_fields()
                yield from self._compose_json_format_editor()

            yield Static("", id="plugin-editor-error")
            with Horizontal(id="plugin-editor-actions"):
                yield Button("取消", id="plugin-editor-cancel")
                actions = self._schema_actions()
                if "validate" in actions:
                    yield Button(
                        "驗證",
                        id="plugin-editor-validate",
                        variant="warning",
                    )
                if "save" in actions:
                    yield Button("儲存", id="plugin-editor-save", variant="primary")

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

        try:
            payload = self._collect_payload()
        except ValueError as e:
            self._show_error(str(e))
            return

        has_error, has_warning, preview = self._evaluate_rule_result(payload)
        if event.button.id == "plugin-editor-validate":
            if has_error:
                self.app.notify(f"❌ 驗證失敗：{preview}", severity="error")
            elif has_warning:
                self.app.notify(f"⚠️ 驗證完成：{preview}", severity="warning")
            else:
                self.app.notify("✅ 驗證通過", severity="information")
            return

        if event.button.id == "plugin-editor-save":
            if has_error:
                self._show_error(preview)
                return
            if has_warning:
                self.app.notify(f"⚠️ 已儲存，請留意：{preview}", severity="warning")
            self.dismiss(payload)

    def _widget_id(self, field_name: str) -> str:
        return f"plugin-field-{field_name}"

    def _compose_dynamic_fields(self) -> ComposeResult:
        for field_name, spec in self._fields.items():
            if not isinstance(spec, dict):
                continue

            required = bool(spec.get("required", False))
            marker = " *" if required else ""
            label = str(spec.get("label", field_name))
            yield Static(f"{label}{marker}", classes="plugin-field-label")
            yield self._build_field_widget(field_name, spec)

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

        if field_type in {"textarea", "list[str]", "list"}:
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
            "JSON 輸出格式（時間欄位固定，其餘可改）",
            classes="plugin-field-label",
        )

        for key, template in self._json_format_examples.items():
            yield Static(f"{key}", classes="plugin-field-label")
            for field_name, field_value in template.items():
                locked = self._is_locked_json_field(field_name)
                lock_suffix = " (固定)" if locked else ""
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
                f"⚠️ 以下範例非 JSON 物件，保留原值: {names}",
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
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        if value is None:
            return ""
        return str(value)

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
            field_label = str(spec.get("label", field_name))
            value = self._collect_field_value(field_name, spec, field_type, field_label)
            self._validate_field_value(spec, field_type, field_label, value)

            if value is not None:
                payload[field_name] = value

        response_json_format = self._collect_response_json_format()
        if response_json_format:
            payload["response_json_format"] = response_json_format

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

        if field_type == "bool":
            return self.query_one(widget_id, Switch).value

        if field_type in {"select", "multiselect"}:
            selector = self.query_one(widget_id, SelectionList)
            selected = [
                option for option in options if option in set(selector.selected)
            ]
            if field_type == "select":
                if len(selected) > 1:
                    raise ValueError(f"{field_label} 只能選一個選項")
                return selected[0] if selected else ""
            return selected

        if field_type == "textarea":
            return str(self.query_one(widget_id, TextArea).text).strip()

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
                raise ValueError(f"{field_label} 必須是整數") from exc

        return self.query_one(widget_id, Input).value.strip()

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
            raise ValueError(f"{field_label} 為必填")

        if field_type == "select" and value and value not in options:
            raise ValueError(f"{field_label} 選項不合法")

        if field_type == "multiselect" and isinstance(value, list):
            illegal = [item for item in value if item not in options]
            if illegal:
                raise ValueError(f"{field_label} 包含不合法選項: {', '.join(illegal)}")

        int_value = (
            value if isinstance(value, int) and not isinstance(value, bool) else None
        )
        if field_type in {"int", "number"} and int_value is not None:
            minimum = spec.get("min")
            maximum = spec.get("max")
            if isinstance(minimum, int) and int_value < minimum:
                raise ValueError(f"{field_label} 不能小於 {minimum}")
            if isinstance(maximum, int) and int_value > maximum:
                raise ValueError(f"{field_label} 不能大於 {maximum}")

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
                raise ValueError(f"{key}.{field_name} 必須是整數")
            try:
                return int(text)
            except ValueError as exc:
                raise ValueError(f"{key}.{field_name} 必須是整數") from exc
        if isinstance(original_value, float):
            text = self.query_one(widget_id, Input).value.strip()
            if not text:
                raise ValueError(f"{key}.{field_name} 必須是數字")
            try:
                return float(text)
            except ValueError as exc:
                raise ValueError(f"{key}.{field_name} 必須是數字") from exc
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
