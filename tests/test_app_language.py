from pathlib import Path
import importlib.util

import pytest
import yaml

from outlook_mail_extractor.i18n import get_language, set_language
from outlook_mail_extractor.runtime import create_runtime_context


def _load_app_class() -> type:
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    spec = importlib.util.spec_from_file_location("app_module", app_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OutlookMailExtractor


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    assert isinstance(data, dict)
    return data


def test_save_ui_language_updates_config(tmp_path: Path) -> None:
    app = _load_app_class()()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("jobs:\n  - name: demo\n", encoding="utf-8")

    app._save_ui_language(config_path, "en-US")

    payload = _load_yaml(config_path)
    assert payload["ui_language"] == "en-US"
    assert isinstance(payload["jobs"], list)


def test_save_ui_language_rejects_non_object_config(tmp_path: Path) -> None:
    app = _load_app_class()()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- invalid\n", encoding="utf-8")

    with pytest.raises(ValueError, match="YAML 物件"):
        app._save_ui_language(config_path, "zh-TW")


def test_first_run_uses_windows_zh_tw_for_tui_text(tmp_path: Path, monkeypatch) -> None:
    runtime = create_runtime_context(project_root=tmp_path)
    app_class = _load_app_class()

    monkeypatch.setitem(
        app_class.compose.__globals__, "get_runtime_context", lambda: runtime
    )
    monkeypatch.setitem(
        app_class.on_mount.__globals__, "get_runtime_context", lambda: runtime
    )
    monkeypatch.setattr(
        "outlook_mail_extractor.i18n.detect_system_language", lambda: "zh-TW"
    )

    set_language("en-US")
    app = app_class()

    next(app.compose())
    app.on_mount()

    assert get_language() == "zh-TW"
    assert app.sub_title == "AI 郵件整理工具"
