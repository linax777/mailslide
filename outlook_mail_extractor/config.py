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
    required_fields = ["name", "account", "filter", "plugins"]
    for field in required_fields:
        if field not in job:
            raise ValueError(f"Job #{idx + 1} missing required field: '{field}'")

    if not isinstance(job["plugins"], list):
        raise ValueError(f"Job #{idx + 1} 'plugins' must be a list")


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


def load_config(config_file: Path | str = "config.yaml") -> dict:
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


def load_filters(filters_file: Path | str = "filters.yaml") -> dict:
    """
    Load filter definitions.

    Args:
        filters_file: Path to filters.yaml

    Returns:
        Dictionary of filter definitions
    """
    filters_path = Path(filters_file)
    if not filters_path.exists():
        return {}

    with open(filters_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_filter(filter_name: str, filters: dict | None = None) -> dict:
    """
    Get filter configuration by name.

    Args:
        filter_name: Name of the filter
        filters: Optional pre-loaded filters dict

    Returns:
        Filter configuration dictionary
    """
    if filters is None:
        filters = load_filters()

    return filters.get(filter_name, filters.get("default", {}))


def apply_filter(messages, filter_config: dict) -> list:
    """
    Apply filter conditions to messages.

    Args:
        messages: Outlook Items collection
        filter_config: Filter configuration dict

    Returns:
        Filtered list of messages
    """
    from .parser import clean_content

    filtered = []

    # Sort by received time (newest first)
    messages.Sort("[ReceivedTime]", True)

    # Get limit from filter
    limit = filter_config.get("limit", 10)

    # Apply filter conditions
    message = messages.GetFirst()
    count = 0

    while message and count < limit:
        if message.Class != 43:  # Not a mail item
            message = messages.GetNext()
            continue

        # Check from
        from_contains = filter_config.get("from_contains")
        if from_contains:
            if isinstance(from_contains, list):
                sender_match = any(
                    from_contains.lower()
                    in str(message.SenderEmailAddress or "").lower()
                    for from_contains in from_contains
                )
            else:
                sender_match = (
                    from_contains.lower()
                    in str(message.SenderEmailAddress or "").lower()
                )
            if not sender_match:
                message = messages.GetNext()
                continue

        # Check subject contains
        subject_contains = filter_config.get("subject_contains")
        if subject_contains:
            if isinstance(subject_contains, list):
                subject_match = any(
                    keyword.lower() in str(message.Subject or "").lower()
                    for keyword in subject_contains
                )
            else:
                subject_match = (
                    subject_contains.lower() in str(message.Subject or "").lower()
                )
            if not subject_match:
                message = messages.GetNext()
                continue

        # Check is_unread
        is_unread = filter_config.get("is_unread")
        if is_unread is not None:
            if is_unread != (message.UnRead == True):
                message = messages.GetNext()
                continue

        # Check importance
        importance = filter_config.get("importance")
        if importance:
            if importance == "high" and message.Importance != 2:  # 2 = high
                message = messages.GetNext()
                continue

        filtered.append(message)
        count += 1
        message = messages.GetNext()

    return filtered
