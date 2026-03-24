import pytest

from outlook_mail_extractor.config import validate_config


def test_validate_config_accepts_supported_ui_language() -> None:
    validate_config(
        {
            "ui_language": "en-US",
            "jobs": [
                {
                    "name": "job-1",
                    "account": "acc@example.com",
                    "source": "Inbox",
                }
            ],
        }
    )


def test_validate_config_rejects_unsupported_ui_language() -> None:
    with pytest.raises(ValueError, match="ui_language"):
        validate_config(
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
