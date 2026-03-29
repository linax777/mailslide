"""View/composition helpers for plugin editor modal."""

from typing import Any


def schema_actions(buttons: list[Any]) -> set[str]:
    """Extract enabled actions from schema button definitions."""
    actions: set[str] = set()
    for button in buttons:
        if not isinstance(button, dict):
            continue
        action = str(button.get("action", "")).strip().lower()
        if action:
            actions.add(action)
    if not actions:
        return {"validate", "save"}
    return actions
