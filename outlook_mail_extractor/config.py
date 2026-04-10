"""Configuration loading and validation module"""

from pathlib import Path

from mailslide.config_models import (
    ConfigValidationError,
    app_config_from_payload,
    app_config_to_payload,
)
from mailslide.config_repository import ConfigRepository

from .config_migration import MigrationResult


_LAST_MIGRATION_RESULT: MigrationResult | None = None


def validate_config(config: dict) -> None:
    """
    Validate main config format.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: When config format is invalid
    """
    try:
        app_config_from_payload(config)
    except ConfigValidationError as error:
        raise ValueError(str(error)) from error


def load_config(config_file: Path | str = "config/config.yaml") -> dict:
    """
    Load and validate main config file.

    Args:
        config_file: Path to config.yaml

    Returns:
        Validated config dictionary
    """
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    repository = ConfigRepository(config_path)

    global _LAST_MIGRATION_RESULT
    try:
        typed_config = repository.load()
    finally:
        _LAST_MIGRATION_RESULT = repository.last_migration_result

    return app_config_to_payload(typed_config)


def get_last_migration_result() -> MigrationResult | None:
    return _LAST_MIGRATION_RESULT
