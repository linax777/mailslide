"""Configuration loading and validation module"""

from pathlib import Path

import yaml


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
