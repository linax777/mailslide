"""Helpers for loading and validating TUI schema metadata from YAML samples."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .i18n import t


@dataclass
class UiRuleResult:
    """Validation result for one UI rule."""

    rule_id: str
    level: str
    message: str
    passed: bool


def load_ui_schema(sample_path: Path | str) -> dict[str, Any]:
    """Load `_ui` schema block from a YAML sample file."""
    path = Path(sample_path)
    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}

    schema = payload.get("_ui", {})
    return schema if isinstance(schema, dict) else {}


def load_plugin_ui_schema(
    plugin_name: str,
    plugins_dir: Path | str,
) -> dict[str, Any]:
    """Load plugin `_ui` schema from `<plugins_dir>/<plugin>.yaml.sample`."""
    plugin_key = str(plugin_name).strip()
    if not plugin_key:
        return {}

    sample_path = Path(plugins_dir) / f"{plugin_key}.yaml.sample"
    return load_ui_schema(sample_path)


def validate_ui_schema(schema: dict[str, Any]) -> list[str]:
    """Perform lightweight structural validation for UI schema."""
    errors: list[str] = []
    if not schema:
        return ["缺少 _ui 區塊"]

    version = schema.get("schema_version")
    if not isinstance(version, int):
        errors.append("_ui.schema_version 必須是整數")

    buttons = schema.get("buttons", [])
    if not isinstance(buttons, list):
        errors.append("_ui.buttons 必須是陣列")
    else:
        for index, button in enumerate(buttons, start=1):
            if not isinstance(button, dict):
                errors.append(f"_ui.buttons[{index}] 必須是物件")
                continue
            for key in ("id", "action"):
                if key not in button:
                    errors.append(f"_ui.buttons[{index}] 缺少 '{key}'")
            if "label" not in button and "label_key" not in button:
                errors.append(f"_ui.buttons[{index}] 缺少 'label' 或 'label_key'")

    fields = schema.get("fields", {})
    if not isinstance(fields, dict):
        errors.append("_ui.fields 必須是物件")

    rules = schema.get("validation_rules", [])
    if not isinstance(rules, list):
        errors.append("_ui.validation_rules 必須是陣列")
    else:
        for index, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict):
                errors.append(f"_ui.validation_rules[{index}] 必須是物件")
                continue
            for key in ("id", "level"):
                if key not in rule:
                    errors.append(f"_ui.validation_rules[{index}] 缺少 '{key}'")
            if "message" not in rule and "message_key" not in rule:
                errors.append(
                    f"_ui.validation_rules[{index}] 缺少 'message' 或 'message_key'"
                )

    return errors


def flatten_ui_fields(
    fields: dict[str, Any],
    prefix: str = "",
) -> list[tuple[str, str, str, bool]]:
    """Flatten nested field definitions for table rendering."""
    rows: list[tuple[str, str, str, bool]] = []
    for field_name, spec in fields.items():
        if not isinstance(spec, dict):
            continue

        path = f"{prefix}{field_name}" if not prefix else f"{prefix}.{field_name}"
        field_type = str(spec.get("type", "unknown"))
        label = schema_text(
            spec, key_field="label_key", fallback_field="label", default=field_name
        )
        required = bool(spec.get("required", False))
        rows.append((path, field_type, label, required))

        item_fields = spec.get("item_fields")
        if isinstance(item_fields, dict):
            nested_prefix = f"{path}[]"
            rows.extend(flatten_ui_fields(item_fields, prefix=nested_prefix))

    return rows


def evaluate_rules(
    config: dict[str, Any], rules: list[dict[str, Any]]
) -> list[UiRuleResult]:
    """Evaluate known built-in rules against runtime config payload."""
    results: list[UiRuleResult] = []
    for rule in rules:
        rule_id = str(rule.get("id", "unknown"))
        level = str(rule.get("level", "warning")).lower()
        message = schema_text(
            rule,
            key_field="message_key",
            fallback_field="message",
            default="",
        )

        evaluator = get_rule_evaluator(rule_id)
        if evaluator is None:
            results.append(
                UiRuleResult(
                    rule_id=rule_id,
                    level=level,
                    message=f"{message} (未實作 evaluator，先略過)",
                    passed=True,
                )
            )
            continue

        try:
            passed = evaluator(config)
        except Exception:
            passed = False

        results.append(
            UiRuleResult(
                rule_id=rule_id,
                level=level,
                message=message,
                passed=passed,
            )
        )

    return results


def schema_text(
    payload: dict[str, Any],
    key_field: str,
    fallback_field: str,
    default: str = "",
) -> str:
    """Resolve schema text via i18n key with plain text fallback."""
    key = payload.get(key_field)
    if isinstance(key, str) and key.strip():
        return t(key.strip())

    value = payload.get(fallback_field, default)
    return str(value)


def build_default_list_item(
    schema: dict[str, Any],
    list_field: str,
) -> dict[str, Any]:
    """Build a default dict item from list field schema."""
    fields = schema.get("fields", {})
    if not isinstance(fields, dict):
        return {}

    list_spec = fields.get(list_field, {})
    if not isinstance(list_spec, dict):
        return {}

    item_fields = list_spec.get("item_fields", {})
    if not isinstance(item_fields, dict):
        return {}

    default_item: dict[str, Any] = {}
    for key, spec in item_fields.items():
        if not isinstance(spec, dict):
            continue

        if "default" in spec:
            default_item[key] = spec["default"]
            continue

        field_type = spec.get("type")
        if field_type == "bool":
            default_item[key] = False
        elif field_type in {"int", "number"}:
            default_item[key] = 0
        elif field_type in {"multiselect", "list", "list[str]"}:
            default_item[key] = []
        else:
            default_item[key] = ""

    return default_item


def strip_reserved_metadata(data: Any) -> Any:
    """Remove reserved metadata keys (e.g. _ui, _meta) recursively."""
    if isinstance(data, dict):
        return {
            key: strip_reserved_metadata(value)
            for key, value in data.items()
            if not (isinstance(key, str) and key.startswith("_"))
        }
    if isinstance(data, list):
        return [strip_reserved_metadata(item) for item in data]
    return data


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _jobs(config: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = config.get("jobs", [])
    return (
        [job for job in jobs if isinstance(job, dict)] if isinstance(jobs, list) else []
    )


def _rule_required_name_account_source(config: dict[str, Any]) -> bool:
    jobs = _jobs(config)
    return all(
        _has_text(job.get("name"))
        and _has_text(job.get("account"))
        and _has_text(job.get("source"))
        for job in jobs
    )


def _rule_limit_positive(config: dict[str, Any]) -> bool:
    for job in _jobs(config):
        limit = job.get("limit")
        if limit is None:
            continue
        if not _is_int(limit) or limit <= 0:
            return False
    return True


def _rule_body_max_length_positive(config: dict[str, Any]) -> bool:
    top_level = config.get("body_max_length")
    if top_level is not None and (not _is_int(top_level) or top_level <= 0):
        return False

    for job in _jobs(config):
        value = job.get("body_max_length")
        if value is None:
            continue
        if not _is_int(value) or value <= 0:
            return False
    return True


def _rule_destination_move_conflict(config: dict[str, Any]) -> bool:
    for job in _jobs(config):
        plugins = job.get("plugins", [])
        plugins_list = plugins if isinstance(plugins, list) else []
        has_move_plugin = "move_to_folder" in plugins_list
        has_destination = _has_text(job.get("destination"))
        if has_move_plugin and has_destination:
            return False
    return True


def _rule_unique_job_name(config: dict[str, Any]) -> bool:
    names = [str(job.get("name", "")).strip() for job in _jobs(config)]
    filtered = [name for name in names if name]
    return len(filtered) == len(set(filtered))


def _rule_at_least_one_enabled(config: dict[str, Any]) -> bool:
    return any(job.get("enable", True) is not False for job in _jobs(config))


def _rule_api_base_required(config: dict[str, Any]) -> bool:
    return _has_text(config.get("api_base"))


def _rule_api_base_url_like(config: dict[str, Any]) -> bool:
    api_base = str(config.get("api_base", ""))
    return api_base.startswith("http://") or api_base.startswith("https://")


def _rule_timeout_range(config: dict[str, Any]) -> bool:
    timeout = config.get("timeout")
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        return False
    timeout_value = int(timeout)
    return 1 <= timeout_value <= 300


def _rule_response_format_enum(config: dict[str, Any]) -> bool:
    return config.get("response_format") in {"json", "text"}


def _rule_output_file_csv(config: dict[str, Any]) -> bool:
    output_file = str(config.get("output_file", "")).lower()
    return output_file.endswith(".csv")


def _rule_output_file_xlsx(config: dict[str, Any]) -> bool:
    output_file = str(config.get("output_file", "")).lower()
    return output_file.endswith(".xlsx")


def _rule_include_fields_not_empty(config: dict[str, Any]) -> bool:
    fields = config.get("include_fields")
    return isinstance(fields, list) and len(fields) > 0


def _rule_required_placeholders(config: dict[str, Any]) -> bool:
    filename_format = str(config.get("filename_format", ""))
    return "{timestamp}" in filename_format


def _rule_recipients_email_like(config: dict[str, Any]) -> bool:
    recipients = config.get("recipients", [])
    if not isinstance(recipients, list):
        return False
    pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    return all(
        isinstance(email, str) and bool(pattern.match(email)) for email in recipients
    )


def _rule_display_level_enum(config: dict[str, Any]) -> bool:
    logging = config.get("logging", {})
    if not isinstance(logging, dict):
        return False
    return logging.get("display_level") in {"DEBUG", "INFO", "WARNING", "ERROR"}


_RULE_EVALUATORS: dict[str, Any] = {
    "required_name_account_source": _rule_required_name_account_source,
    "limit_positive": _rule_limit_positive,
    "body_max_length_positive": _rule_body_max_length_positive,
    "destination_move_conflict": _rule_destination_move_conflict,
    "unique_job_name": _rule_unique_job_name,
    "at_least_one_enabled": _rule_at_least_one_enabled,
    "api_base_required": _rule_api_base_required,
    "api_base_url_like": _rule_api_base_url_like,
    "timeout_range": _rule_timeout_range,
    "response_format_enum": _rule_response_format_enum,
    "output_file_csv": _rule_output_file_csv,
    "output_file_xlsx": _rule_output_file_xlsx,
    "include_fields_not_empty": _rule_include_fields_not_empty,
    "required_placeholders": _rule_required_placeholders,
    "recipients_email_like": _rule_recipients_email_like,
    "display_level_enum": _rule_display_level_enum,
}


def register_rule_evaluator(rule_id: str, evaluator: Any) -> None:
    """Register or replace a UI schema rule evaluator."""
    key = str(rule_id).strip()
    if not key:
        raise ValueError("rule_id is required")
    if not callable(evaluator):
        raise ValueError("evaluator must be callable")
    _RULE_EVALUATORS[key] = evaluator


def get_rule_evaluator(rule_id: str) -> Any | None:
    """Get a registered UI schema rule evaluator by id."""
    return _RULE_EVALUATORS.get(str(rule_id).strip())


def list_rule_evaluators() -> list[str]:
    """List currently registered UI schema rule evaluator ids."""
    return sorted(_RULE_EVALUATORS.keys())
