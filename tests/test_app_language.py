from pathlib import Path
import importlib.util

import pytest
import yaml


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
