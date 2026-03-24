"""Tests for UI schema helpers."""

from outlook_mail_extractor.ui_schema import (
    build_default_list_item,
    evaluate_rules,
    flatten_ui_fields,
    load_plugin_ui_schema,
    schema_text,
    strip_reserved_metadata,
    validate_ui_schema,
)
from outlook_mail_extractor.i18n import set_language


def test_flatten_ui_fields_supports_list_item_fields() -> None:
    """Flatten nested `item_fields` for list type fields."""
    fields = {
        "jobs": {
            "type": "list",
            "item_fields": {
                "name": {"type": "str", "label": "工作名稱", "required": True},
                "limit": {"type": "int", "label": "上限", "required": False},
            },
        }
    }

    rows = flatten_ui_fields(fields)

    assert ("jobs", "list", "jobs", False) in rows
    assert ("jobs[].name", "str", "工作名稱", True) in rows
    assert ("jobs[].limit", "int", "上限", False) in rows


def test_evaluate_rules_reports_main_config_conflicts() -> None:
    """Detect destination and move_to_folder conflict from schema rules."""
    config = {
        "jobs": [
            {
                "name": "job-1",
                "account": "a@example.com",
                "source": "Inbox",
                "destination": "Inbox/done",
                "plugins": ["move_to_folder"],
                "enable": True,
                "limit": 10,
            }
        ]
    }
    rules = [
        {
            "id": "destination_move_conflict",
            "level": "error",
            "message": "conflict",
        }
    ]

    results = evaluate_rules(config, rules)

    assert len(results) == 1
    assert results[0].rule_id == "destination_move_conflict"
    assert results[0].passed is False


def test_build_default_list_item_reads_defaults_from_schema() -> None:
    """Create default list item using schema-defined defaults and types."""
    schema = {
        "fields": {
            "jobs": {
                "type": "list",
                "item_fields": {
                    "name": {"type": "str", "default": ""},
                    "enable": {"type": "bool", "default": True},
                    "limit": {"type": "int", "default": 10},
                    "plugins": {"type": "multiselect"},
                },
            }
        }
    }

    default_item = build_default_list_item(schema, "jobs")

    assert default_item["enable"] is True
    assert default_item["limit"] == 10
    assert default_item["plugins"] == []


def test_strip_reserved_metadata_removes_ui_keys_recursively() -> None:
    """Drop keys starting with underscore from nested payloads."""
    payload = {
        "jobs": [{"name": "A", "_meta": {"x": 1}}],
        "_ui": {"schema_version": 1},
        "logging": {"display_level": "DEBUG", "_note": "internal"},
    }

    sanitized = strip_reserved_metadata(payload)

    assert "_ui" not in sanitized
    assert "_note" not in sanitized["logging"]
    assert "_meta" not in sanitized["jobs"][0]


def test_load_plugin_ui_schema_reads_schema_from_sample(tmp_path) -> None:
    """Load plugin `_ui` schema from plugin sample file."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir(parents=True)
    sample_path = plugins_dir / "demo.yaml.sample"
    sample_path.write_text(
        """
enabled: true
_ui:
  schema_version: 1
  fields:
    enabled:
      type: bool
""".strip(),
        encoding="utf-8",
    )

    schema = load_plugin_ui_schema("demo", plugins_dir)

    assert schema["schema_version"] == 1
    assert schema["fields"]["enabled"]["type"] == "bool"


def test_load_plugin_ui_schema_returns_empty_when_missing_sample(tmp_path) -> None:
    """Return empty dict when plugin sample file does not exist."""
    schema = load_plugin_ui_schema("missing", tmp_path)
    assert schema == {}


def test_validate_ui_schema_accepts_label_key_and_message_key() -> None:
    schema = {
        "schema_version": 1,
        "buttons": [
            {
                "id": "save",
                "label_key": "ui.main.button.save",
                "action": "save",
            }
        ],
        "fields": {},
        "validation_rules": [
            {
                "id": "limit_positive",
                "level": "error",
                "message_key": "ui.main.rule.limit_positive",
            }
        ],
    }

    assert validate_ui_schema(schema) == []


def test_schema_text_prefers_key_when_available() -> None:
    set_language("zh-TW")
    payload = {
        "label_key": "ui.main.button.save",
        "label": "fallback",
    }
    assert schema_text(payload, "label_key", "label", "") == "儲存"
