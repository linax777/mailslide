from pathlib import Path

import yaml

from outlook_mail_extractor.i18n import resolve_language, set_language, t


def test_translate_by_key_in_zh_tw() -> None:
    set_language("zh-TW")
    assert t("app.title") == "Outlook Mail Extractor"
    assert t("app.confirm_quit.message") == "確定要結束程式嗎？"


def test_translate_by_key_in_en_us() -> None:
    set_language("en-US")
    assert t("app.subtitle") == "Extract email body content"
    assert t("app.confirm_quit.yes") == "Quit"


def test_unknown_key_returns_key() -> None:
    set_language("en-US")
    assert t("unknown.translation.key") == "unknown.translation.key"


def test_resolve_language_from_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"ui_language": "en-US"}, f)

    assert resolve_language(config_path) == "en-US"


def test_resolve_language_fallback_for_invalid_value(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"ui_language": "jp-JP"}, f)

    assert resolve_language(config_path) == "zh-TW"
