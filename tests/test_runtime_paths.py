from pathlib import Path

from outlook_mail_extractor.runtime import build_runtime_paths, create_runtime_context


def test_build_runtime_paths_uses_user_data_dir_override(
    monkeypatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "user-data"
    monkeypatch.setenv("MAILSLIDE_DATA_DIR", str(data_root))

    paths = build_runtime_paths(project_root=None)

    assert paths.config_dir == data_root / "config"
    assert paths.logs_dir == data_root / "logs"
    assert paths.config_file == data_root / "config" / "config.yaml"


def test_create_runtime_context_seeds_sample_files(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "user-data"
    monkeypatch.setenv("MAILSLIDE_DATA_DIR", str(data_root))

    runtime = create_runtime_context(project_root=None)

    assert runtime.paths.config_dir == data_root / "config"
    assert (runtime.paths.config_dir / "config.yaml.sample").exists()
    assert (runtime.paths.config_dir / "plugins" / "summary_file.yaml.sample").exists()
