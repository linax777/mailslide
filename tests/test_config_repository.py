from pathlib import Path

import yaml

from mailslide.config_models import AppConfig, JobConfig
from mailslide.config_repository import ConfigRepository
from outlook_mail_extractor.config import get_last_migration_result, load_config
from outlook_mail_extractor.config_migration import LATEST_CONFIG_VERSION
from outlook_mail_extractor.tui import OutlookMailExtractor


def _read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    assert isinstance(data, dict)
    return data


def test_config_repository_load_migrates_and_returns_typed_config(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "jobs:\n  - name: demo\n    account: acc@example.com\n    source: Inbox\n",
        encoding="utf-8",
    )

    repo = ConfigRepository(config_path)

    config = repo.load()

    assert isinstance(config, AppConfig)
    assert config.config_version == LATEST_CONFIG_VERSION
    assert config.jobs[0].extras["batch_flush_enabled"] is True
    persisted = _read_yaml(config_path)
    assert persisted["config_version"] == LATEST_CONFIG_VERSION


def test_config_repository_save_writes_and_creates_yaml_bak(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "config_version: 2\n"
        "ui_language: zh-TW\n"
        "jobs:\n"
        "  - name: demo\n"
        "    account: acc@example.com\n"
        "    source: Inbox\n",
        encoding="utf-8",
    )

    repo = ConfigRepository(config_path)
    repo.save(
        AppConfig(
            jobs=[
                JobConfig(
                    name="demo",
                    account="acc@example.com",
                    source="Inbox",
                )
            ],
            config_version=LATEST_CONFIG_VERSION,
            ui_language="en-US",
        )
    )

    backup_path = config_path.with_suffix(".yaml.bak")
    assert backup_path.exists()
    assert "ui_language: zh-TW" in backup_path.read_text(encoding="utf-8")
    payload = _read_yaml(config_path)
    assert payload["ui_language"] == "en-US"


def test_load_config_bridge_uses_repository_and_returns_payload(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "jobs:\n  - name: demo\n    account: acc@example.com\n    source: Inbox\n",
        encoding="utf-8",
    )

    payload = load_config(config_path)

    assert payload["config_version"] == LATEST_CONFIG_VERSION
    assert payload["jobs"][0]["batch_flush_enabled"] is True
    migration = get_last_migration_result()
    assert migration is not None
    assert migration.changed is True


def test_tui_save_ui_language_uses_yaml_backup_flow(tmp_path: Path) -> None:
    app = OutlookMailExtractor()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "config_version: 2\n"
        "jobs:\n"
        "  - name: demo\n"
        "    account: acc@example.com\n"
        "    source: Inbox\n",
        encoding="utf-8",
    )

    app._save_ui_language(config_path, "en-US")

    payload = _read_yaml(config_path)
    assert payload["ui_language"] == "en-US"
    assert config_path.with_suffix(".yaml.bak").exists()
