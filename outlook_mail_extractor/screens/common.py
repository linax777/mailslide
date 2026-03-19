"""Shared utilities for screen modules."""

MAX_CELL_LENGTH = 25


def truncate(text: str | None, max_len: int = MAX_CELL_LENGTH) -> str:
    if text is None:
        return ""
    if len(text) > max_len:
        return text[: max_len - 2] + ".."
    return text


LEVEL_PRIORITY = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
