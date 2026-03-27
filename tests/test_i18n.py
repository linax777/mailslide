from pathlib import Path

import yaml

from outlook_mail_extractor.i18n import resolve_language, set_language, t


def test_translate_by_key_in_zh_tw() -> None:
    set_language("zh-TW")
    assert t("app.title") == "Mailslide for Outlook Classic"
    assert t("app.confirm_quit.message") == "確定要結束程式嗎？"


def test_translate_by_key_in_en_us() -> None:
    set_language("en-US")
    assert t("app.subtitle") == "AI powered mail organizer"
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

    assert resolve_language(config_path) == "en-US"


def test_resolve_language_uses_system_language_when_config_missing(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "missing.yaml"
    monkeypatch.setattr(
        "outlook_mail_extractor.i18n.detect_system_language", lambda: "zh-TW"
    )
    assert resolve_language(config_path) == "zh-TW"


def test_resolve_language_uses_system_language_when_ui_language_missing(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"jobs": []}, f)

    monkeypatch.setattr(
        "outlook_mail_extractor.i18n.detect_system_language", lambda: "zh-TW"
    )
    assert resolve_language(config_path) == "zh-TW"
