"""Configuration loading and validation module"""

from pathlib import Path

import yaml


_ALLOWED_LLM_MODES = {
    "per_plugin",
    "share_deprecated",
    "shared",
    "shared_legacy",
}


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

    if "body_max_length" in config:
        _validate_body_max_length(config["body_max_length"], "Config")

    if "llm_mode" in config:
        _validate_llm_mode(config["llm_mode"], "Config")

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

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    validate_config(config)
    return config
