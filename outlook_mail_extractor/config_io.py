"""Shared YAML I/O helpers for app config files."""

from pathlib import Path
from typing import Any

import yaml


def dump_yaml_text(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def write_yaml_with_backup(
    target_path: Path,
    payload: dict[str, Any],
    *,
    backup_path: Path | None = None,
) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)

    resolved_backup = backup_path or target_path.with_suffix(".yaml.bak")
    if target_path.exists():
        resolved_backup.write_text(
            target_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    dumped = dump_yaml_text(payload)
    temp_path = target_path.with_name(f".{target_path.name}.tmp")
    temp_path.write_text(dumped, encoding="utf-8")
    temp_path.replace(target_path)
    return target_path
