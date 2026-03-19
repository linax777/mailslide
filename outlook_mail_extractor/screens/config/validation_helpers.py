"""Validation helpers for schema-driven config tabs."""

from typing import Any


def collect_rule_failures(results: list[Any]) -> tuple[list[str], list[str]]:
    """Collect failed error/warning messages from rule results.

    Args:
        results: Return value from `evaluate_rules`.

    Returns:
        Tuple of `(failed_errors, failed_warnings)`.
    """
    failed_errors: list[str] = []
    failed_warnings: list[str] = []
    for result in results:
        if result.passed:
            continue
        if result.level == "error":
            failed_errors.append(result.message)
        else:
            failed_warnings.append(result.message)
    return failed_errors, failed_warnings


def preview_messages(messages: list[str], limit: int = 2) -> str:
    """Build compact preview text for notifications.

    Args:
        messages: Message list.
        limit: Max message count in preview.

    Returns:
        Preview string joined by Chinese semicolon.
    """
    return "；".join(messages[:limit])
