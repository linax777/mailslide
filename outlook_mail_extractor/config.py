"""Configuration loading and validation module"""

from pathlib import Path

from .config_migration import (
    LATEST_CONFIG_VERSION,
    MigrationResult,
    migrate_config_file,
)


_ALLOWED_LLM_MODES = {
    "per_plugin",
    "share_deprecated",
    "shared",
    "shared_legacy",
}

_ALLOWED_UI_LANGUAGES = {
    "zh-TW",
    "en-US",
}

_LAST_MIGRATION_RESULT: MigrationResult | None = None


def _validate_body_max_length(value: int, location: str) -> None:
    """Validate body_max_length value."""
    if not isinstance(value, int):
        raise ValueError(f"{location}.body_max_length must be an integer")
    if value <= 0:
        raise ValueError(f"{location}.body_max_length must be > 0")


def _validate_llm_mode(value: str, location: str) -> None:
    """Validate llm_mode value."""
    if not isinstance(value, str):
        raise ValueError(f"{location}.llm_mode must be a string")
    if value not in _ALLOWED_LLM_MODES:
        allowed = ", ".join(sorted(_ALLOWED_LLM_MODES))
        raise ValueError(f"{location}.llm_mode must be one of: {allowed}")


def _validate_ui_language(value: str) -> None:
    """Validate UI language value."""
    if not isinstance(value, str):
        raise ValueError("Config.ui_language must be a string")

    normalized = value.strip().replace("_", "-")
    if normalized not in _ALLOWED_UI_LANGUAGES:
        allowed = ", ".join(sorted(_ALLOWED_UI_LANGUAGES))
        raise ValueError(f"Config.ui_language must be one of: {allowed}")


def validate_job(job: dict, idx: int) -> None:
    """
    Validate a single job configuration.

    Args:
        job: Job configuration dictionary
        idx: Job index (for error messages)

    Raises:
        ValueError: When required fields are missing
    """
    required_fields = ["name", "account", "source"]
    for field in required_fields:
        if field not in job:
            raise ValueError(f"Job #{idx + 1} missing required field: '{field}'")

    if "body_max_length" in job:
        _validate_body_max_length(job["body_max_length"], f"Job #{idx + 1}")

    if "llm_mode" in job:
        _validate_llm_mode(job["llm_mode"], f"Job #{idx + 1}")


def validate_config(config: dict) -> None:
    """
    Validate main config format.

    Args:
        config: Configuration dictionary

    Raises:
        ValueError: When config format is invalid
    """
    if "jobs" not in config:
        raise ValueError("Config missing 'jobs' field")

    if "config_version" in config:
        version = config["config_version"]
        if not isinstance(version, int):
            raise ValueError("Config.config_version must be an integer")
        if version != LATEST_CONFIG_VERSION:
            raise ValueError(
                "Config.config_version mismatch: "
                f"expected {LATEST_CONFIG_VERSION}, got {version}"
            )

    if "body_max_length" in config:
        _validate_body_max_length(config["body_max_length"], "Config")

    if "llm_mode" in config:
        _validate_llm_mode(config["llm_mode"], "Config")

    if "ui_language" in config:
        _validate_ui_language(config["ui_language"])

    for idx, job in enumerate(config["jobs"]):
        validate_job(job, idx)


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

    global _LAST_MIGRATION_RESULT
    config, _LAST_MIGRATION_RESULT = migrate_config_file(config_path)

    validate_config(config)
    return config


def get_last_migration_result() -> MigrationResult | None:
    return _LAST_MIGRATION_RESULT
