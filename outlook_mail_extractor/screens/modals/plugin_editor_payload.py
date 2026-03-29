"""Payload-focused helpers for plugin editor modal."""

import json
from typing import Any


def extract_json_format_raw(config: dict[str, Any]) -> dict[str, str]:
    """Extract and normalize raw ``response_json_format`` payload."""
    json_format = config.get("response_json_format", {})
    if not isinstance(json_format, dict):
        return {}
    return {str(key): str(value) for key, value in json_format.items()}


def parse_json_format_examples(
    raw: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Parse JSON template examples and return unparsable keys."""
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
