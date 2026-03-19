"""Tests for UI schema helpers."""

from outlook_mail_extractor.ui_schema import (
    build_default_list_item,
    evaluate_rules,
    flatten_ui_fields,
    strip_reserved_metadata,
)


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
