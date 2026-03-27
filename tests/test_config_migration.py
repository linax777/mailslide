from pathlib import Path

import pytest
import yaml

from outlook_mail_extractor.config import load_config
from outlook_mail_extractor.config_migration import (
    LATEST_CONFIG_VERSION,
    migrate_config_file,
    migrate_config_payload,
)


def _read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    assert isinstance(data, dict)
    return data


def test_migrate_payload_v0_to_v2_adds_config_defaults() -> None:
    payload = {
        "jobs": [
            {
                "name": "demo",
                "account": "acc@example.com",
                "source": "Inbox",
            }
        ]
    }

    migrated, result = migrate_config_payload(payload)

    assert result.changed is True
    assert result.from_version == 0
    assert result.to_version == LATEST_CONFIG_VERSION
    assert migrated["config_version"] == 2
    assert migrated["jobs"][0]["batch_flush_enabled"] is True


def test_migrate_payload_v1_to_v2_adds_missing_batch_flush_enabled() -> None:
    payload = {
        "config_version": 1,
        "jobs": [
            {
                "name": "demo",
                "account": "acc@example.com",
                "source": "Inbox",
            },
            {
                "name": "keep-existing",
                "account": "acc@example.com",
                "source": "Inbox",
                "batch_flush_enabled": False,
            },
        ],
    }

    migrated, result = migrate_config_payload(payload)

    assert result.changed is True
    assert result.from_version == 1
    assert result.to_version == 2
    assert migrated["jobs"][0]["batch_flush_enabled"] is True
    assert migrated["jobs"][1]["batch_flush_enabled"] is False


def test_migrate_file_creates_backup_and_writes_latest_version(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "jobs:\n  - name: demo\n    account: acc@example.com\n    source: Inbox\n",
        encoding="utf-8",
    )

    migrated, result = migrate_config_file(config_path)

    assert result.changed is True
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert "jobs:" in result.backup_path.read_text(encoding="utf-8")
    assert migrated["config_version"] == LATEST_CONFIG_VERSION

    persisted = _read_yaml(config_path)
    assert persisted["config_version"] == LATEST_CONFIG_VERSION


def test_migrate_file_no_change_for_latest_version(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "config_version: 2\n"
        "jobs:\n"
        "  - name: demo\n"
        "    account: acc@example.com\n"
        "    source: Inbox\n",
        encoding="utf-8",
    )

    _, result = migrate_config_file(config_path)

    assert result.changed is False
    assert result.backup_path is None


def test_load_config_auto_migrates_legacy_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "jobs:\n  - name: demo\n    account: acc@example.com\n    source: Inbox\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["config_version"] == LATEST_CONFIG_VERSION
    assert config["jobs"][0]["batch_flush_enabled"] is True
    persisted = _read_yaml(config_path)
    assert persisted["config_version"] == LATEST_CONFIG_VERSION
    assert persisted["jobs"][0]["batch_flush_enabled"] is True


def test_migrate_payload_rejects_future_config_version() -> None:
    payload = {
        "config_version": 999,
        "jobs": [
            {
                "name": "demo",
                "account": "acc@example.com",
                "source": "Inbox",
            }
        ],
    }

    with pytest.raises(ValueError, match="newer than this app supports"):
        migrate_config_payload(payload)
