"""Typed repository for app config file access."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mailslide.config_models import (
    AppConfig,
    app_config_from_payload,
    app_config_to_payload,
)

if TYPE_CHECKING:
    from outlook_mail_extractor.config_migration import MigrationResult


class ConfigRepository:
    def __init__(self, config_path: Path | str):
        self._config_path = Path(config_path)
        self.last_migration_result: MigrationResult | None = None

    def load(self) -> AppConfig:
        from outlook_mail_extractor.config_migration import migrate_config_file

        payload, migration_result = migrate_config_file(self._config_path)
        self.last_migration_result = migration_result
        return app_config_from_payload(payload)

    def save(self, config: AppConfig) -> None:
        from outlook_mail_extractor.config_io import write_yaml_with_backup

        payload = app_config_to_payload(config)
        write_yaml_with_backup(
            self._config_path,
            payload,
            backup_path=self._config_path.with_suffix(".yaml.bak"),
        )
