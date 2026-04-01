from pathlib import Path

from outlook_mail_extractor.config_templates import (
    all_configs_initialized,
    ensure_config_samples,
    initialize_configs,
)


def test_ensure_config_samples_copies_packaged_templates(tmp_path: Path) -> None:
    copied = ensure_config_samples(tmp_path)

    assert copied > 0
    assert (tmp_path / "config.yaml.sample").exists()
    assert (tmp_path / "plugins" / "add_category.yaml.sample").exists()
    assert (tmp_path / "plugins" / "download_attachments.yaml.sample").exists()

    download_sample = (
        tmp_path / "plugins" / "download_attachments.yaml.sample"
    ).read_text(encoding="utf-8")
    assert "filename_max_length_floor" in download_sample


def test_initialize_configs_creates_yaml_and_is_idempotent(tmp_path: Path) -> None:
    copied, skipped = initialize_configs(tmp_path)

    assert copied > 0
    assert skipped == 0
    assert (tmp_path / "config.yaml").exists()
    assert (tmp_path / "plugins" / "write_file.yaml").exists()
    assert all_configs_initialized(tmp_path)

    copied_again, skipped_again = initialize_configs(tmp_path)
    assert copied_again == 0
    assert skipped_again >= copied
