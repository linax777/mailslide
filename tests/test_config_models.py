from __future__ import annotations

import pytest

import outlook_mail_extractor.config as config_module
from mailslide.config_models import (
    ConfigValidationError,
    app_config_from_payload,
    app_config_to_payload,
)
from outlook_mail_extractor.config import validate_config


def test_app_config_from_payload_round_trip_keeps_extra_fields() -> None:
    payload = {
        "config_version": 2,
        "body_max_length": 1200,
        "llm_mode": "per_plugin",
        "ui_language": "zh-TW",
        "terminal_title": "Demo",
        "jobs": [
            {
                "name": "job-1",
                "account": "acc@example.com",
                "source": "Inbox",
                "llm_mode": "share_deprecated",
                "batch_flush_enabled": True,
            }
        ],
    }

    config = app_config_from_payload(payload)

    assert config.jobs[0].name == "job-1"
    assert config.jobs[0].llm_mode == "share_deprecated"

    serialized = app_config_to_payload(config)
    assert serialized == payload


def test_app_config_from_payload_rejects_unknown_llm_mode() -> None:
    with pytest.raises(ConfigValidationError, match="Config.llm_mode"):
        app_config_from_payload(
            {
                "llm_mode": "invalid",
                "jobs": [
                    {
                        "name": "job-1",
                        "account": "acc@example.com",
                        "source": "Inbox",
                    }
                ],
            }
        )


def test_app_config_from_payload_rejects_unknown_job_llm_mode() -> None:
    with pytest.raises(ConfigValidationError, match="Job #1.llm_mode"):
        app_config_from_payload(
            {
                "jobs": [
                    {
                        "name": "job-1",
                        "account": "acc@example.com",
                        "source": "Inbox",
                        "llm_mode": "invalid",
                    }
                ]
            }
        )


def test_app_config_from_payload_rejects_unsupported_ui_language() -> None:
    with pytest.raises(ConfigValidationError, match="ui_language"):
        app_config_from_payload(
            {
                "ui_language": "ja-JP",
                "jobs": [
                    {
                        "name": "job-1",
                        "account": "acc@example.com",
                        "source": "Inbox",
                    }
                ],
            }
        )


def test_validate_config_maps_config_validation_error_to_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(_: dict[str, object]) -> None:
        raise ConfigValidationError("boom")

    monkeypatch.setattr(config_module, "app_config_from_payload", _raise)

    with pytest.raises(ValueError, match="boom"):
        validate_config(
            {
                "jobs": [
                    {
                        "name": "job-1",
                        "account": "acc@example.com",
                        "source": "Inbox",
                    }
                ]
            }
        )


def test_validate_config_rejects_config_version_mismatch() -> None:
    with pytest.raises(ValueError, match="config_version mismatch"):
        validate_config(
            {
                "config_version": 999,
                "jobs": [
                    {
                        "name": "job-1",
                        "account": "acc@example.com",
                        "source": "Inbox",
                    }
                ],
            }
        )


def test_validate_config_rejects_invalid_body_max_length() -> None:
    with pytest.raises(ValueError, match="body_max_length"):
        validate_config(
            {
                "body_max_length": 0,
                "jobs": [
                    {
                        "name": "job-1",
                        "account": "acc@example.com",
                        "source": "Inbox",
                    }
                ],
            }
        )


def test_validate_config_rejects_missing_required_job_field() -> None:
    with pytest.raises(ValueError, match="missing required field"):
        validate_config(
            {
                "jobs": [
                    {
                        "name": "job-1",
                        "source": "Inbox",
                    }
                ],
            }
        )


def test_validate_config_rejects_invalid_job_llm_mode() -> None:
    with pytest.raises(ValueError, match="Job #1.llm_mode"):
        validate_config(
            {
                "jobs": [
                    {
                        "name": "job-1",
                        "account": "acc@example.com",
                        "source": "Inbox",
                        "llm_mode": "bad-mode",
                    }
                ],
            }
        )
