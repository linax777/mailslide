"""Typed configuration models and payload converters."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Any


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


class ConfigValidationError(ValueError):
    """Raised when config payload fails model validation."""


@dataclass
class JobConfig:
    name: str
    account: str
    source: str
    body_max_length: int | None = None
    llm_mode: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    jobs: list[JobConfig]
    config_version: int | None = None
    body_max_length: int | None = None
    llm_mode: str | None = None
    ui_language: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def _latest_config_version() -> int:
    migration = import_module("outlook_mail_extractor.config_migration")
    version = getattr(migration, "LATEST_CONFIG_VERSION")
    return int(version)


def _validate_body_max_length(value: int, location: str) -> None:
    if not isinstance(value, int):
        raise ConfigValidationError(f"{location}.body_max_length must be an integer")
    if value <= 0:
        raise ConfigValidationError(f"{location}.body_max_length must be > 0")


def _validate_llm_mode(value: str, location: str) -> None:
    if not isinstance(value, str):
        raise ConfigValidationError(f"{location}.llm_mode must be a string")
    if value not in _ALLOWED_LLM_MODES:
        allowed = ", ".join(sorted(_ALLOWED_LLM_MODES))
        raise ConfigValidationError(f"{location}.llm_mode must be one of: {allowed}")


def _validate_ui_language(value: str) -> None:
    if not isinstance(value, str):
        raise ConfigValidationError("Config.ui_language must be a string")

    normalized = value.strip().replace("_", "-")
    if normalized not in _ALLOWED_UI_LANGUAGES:
        allowed = ", ".join(sorted(_ALLOWED_UI_LANGUAGES))
        raise ConfigValidationError(f"Config.ui_language must be one of: {allowed}")


def app_config_from_payload(payload: dict[str, Any]) -> AppConfig:
    if "jobs" not in payload:
        raise ConfigValidationError("Config missing 'jobs' field")

    jobs_payload = payload["jobs"]
    if not isinstance(jobs_payload, list):
        raise ConfigValidationError("Config.jobs must be a list")

    config_version = None
    if "config_version" in payload:
        latest_config_version = _latest_config_version()
        config_version = payload["config_version"]
        if not isinstance(config_version, int):
            raise ConfigValidationError("Config.config_version must be an integer")
        if config_version != latest_config_version:
            raise ConfigValidationError(
                "Config.config_version mismatch: "
                f"expected {latest_config_version}, got {config_version}"
            )

    body_max_length = None
    if "body_max_length" in payload:
        body_max_length = payload["body_max_length"]
        _validate_body_max_length(body_max_length, "Config")

    llm_mode = None
    if "llm_mode" in payload:
        llm_mode = payload["llm_mode"]
        _validate_llm_mode(llm_mode, "Config")

    ui_language = None
    if "ui_language" in payload:
        ui_language = payload["ui_language"]
        _validate_ui_language(ui_language)

    jobs: list[JobConfig] = []
    for idx, raw_job in enumerate(jobs_payload):
        if not isinstance(raw_job, dict):
            raise ConfigValidationError(f"Job #{idx + 1} must be an object")

        for field_name in ("name", "account", "source"):
            if field_name not in raw_job:
                raise ConfigValidationError(
                    f"Job #{idx + 1} missing required field: '{field_name}'"
                )

        job_body_max_length = raw_job.get("body_max_length")
        if "body_max_length" in raw_job:
            _validate_body_max_length(raw_job["body_max_length"], f"Job #{idx + 1}")

        job_llm_mode = raw_job.get("llm_mode")
        if "llm_mode" in raw_job:
            _validate_llm_mode(raw_job["llm_mode"], f"Job #{idx + 1}")

        job_extras = {
            key: value
            for key, value in raw_job.items()
            if key not in {"name", "account", "source", "body_max_length", "llm_mode"}
        }
        jobs.append(
            JobConfig(
                name=raw_job["name"],
                account=raw_job["account"],
                source=raw_job["source"],
                body_max_length=job_body_max_length,
                llm_mode=job_llm_mode,
                extras=job_extras,
            )
        )

    app_extras = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "config_version",
            "body_max_length",
            "llm_mode",
            "ui_language",
            "jobs",
        }
    }

    return AppConfig(
        jobs=jobs,
        config_version=config_version,
        body_max_length=body_max_length,
        llm_mode=llm_mode,
        ui_language=ui_language,
        extras=app_extras,
    )


def app_config_to_payload(config: AppConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if config.config_version is not None:
        payload["config_version"] = config.config_version
    if config.body_max_length is not None:
        payload["body_max_length"] = config.body_max_length
    if config.llm_mode is not None:
        payload["llm_mode"] = config.llm_mode
    if config.ui_language is not None:
        payload["ui_language"] = config.ui_language

    payload.update(config.extras)

    jobs: list[dict[str, Any]] = []
    for job in config.jobs:
        job_payload: dict[str, Any] = {
            "name": job.name,
            "account": job.account,
            "source": job.source,
        }
        if job.body_max_length is not None:
            job_payload["body_max_length"] = job.body_max_length
        if job.llm_mode is not None:
            job_payload["llm_mode"] = job.llm_mode
        job_payload.update(job.extras)
        jobs.append(job_payload)

    payload["jobs"] = jobs
    return payload
