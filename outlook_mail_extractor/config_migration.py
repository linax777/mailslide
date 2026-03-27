"""Config schema migration helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

LATEST_CONFIG_VERSION = 2


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of config migration."""

    changed: bool
    from_version: int
    to_version: int
    backup_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


def _resolve_config_version(payload: dict) -> int:
    raw = payload.get("config_version", 0)
    if raw is None:
        return 0
    if not isinstance(raw, int):
        raise ValueError("Config.config_version must be an integer")
    if raw < 0:
        raise ValueError("Config.config_version must be >= 0")
    return raw


def _migrate_0_to_1(payload: dict) -> None:
    payload["config_version"] = 1


def _migrate_1_to_2(payload: dict) -> None:
    jobs = payload.get("jobs", [])
    if isinstance(jobs, list):
        for job in jobs:
            if isinstance(job, dict) and "batch_flush_enabled" not in job:
                job["batch_flush_enabled"] = True
    payload["config_version"] = 2


def migrate_config_payload(payload: dict) -> tuple[dict, MigrationResult]:
    """Migrate config payload to latest schema version."""
    if not isinstance(payload, dict):
        raise ValueError("Config root must be a YAML object")

    migrated = deepcopy(payload)
    current_version = _resolve_config_version(migrated)
    from_version = current_version

    if current_version > LATEST_CONFIG_VERSION:
        raise ValueError(
            "Config version is newer than this app supports: "
            f"{current_version} > {LATEST_CONFIG_VERSION}"
        )

    while current_version < LATEST_CONFIG_VERSION:
        if current_version == 0:
            _migrate_0_to_1(migrated)
            current_version = 1
            continue
        if current_version == 1:
            _migrate_1_to_2(migrated)
            current_version = 2
            continue
        raise ValueError(f"Missing migration path from v{current_version}")

    return migrated, MigrationResult(
        changed=(migrated != payload),
        from_version=from_version,
        to_version=current_version,
    )


def _dump_yaml(payload: dict) -> str:
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def _backup_path_for(config_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return config_path.with_name(f"{config_path.name}.bak.{timestamp}")


def migrate_config_file(config_path: Path) -> tuple[dict, MigrationResult]:
    """Migrate config file in-place when schema changes are required."""
    original_text = config_path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(original_text)
    payload = loaded if isinstance(loaded, dict) else {}

    migrated_payload, result = migrate_config_payload(payload)
    if not result.changed:
        return migrated_payload, result

    backup_path = _backup_path_for(config_path)
    backup_path.write_text(original_text, encoding="utf-8")

    tmp_path = config_path.with_name(f".{config_path.name}.tmp")
    tmp_path.write_text(_dump_yaml(migrated_payload), encoding="utf-8")
    tmp_path.replace(config_path)

    return migrated_payload, MigrationResult(
        changed=True,
        from_version=result.from_version,
        to_version=result.to_version,
        backup_path=backup_path,
        warnings=result.warnings,
    )
