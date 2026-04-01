"""Helpers for packaged config templates and first-run initialization."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

SAMPLE_SUFFIX = ".yaml.sample"

_SAMPLE_FILES: tuple[Path, ...] = (
    Path("config.yaml.sample"),
    Path("llm-config.yaml.sample"),
    Path("logging.yaml.sample"),
    Path("plugins/add_category.yaml.sample"),
    Path("plugins/create_appointment.yaml.sample"),
    Path("plugins/download_attachments.yaml.sample"),
    Path("plugins/event_table.yaml.sample"),
    Path("plugins/move_to_folder.yaml.sample"),
    Path("plugins/summary_file.yaml.sample"),
    Path("plugins/write_file.yaml.sample"),
)


def _read_template_text(relative_path: Path, project_root: Path | None) -> str:
    if project_root is not None:
        source_path = project_root / "config" / relative_path
        if source_path.exists():
            return source_path.read_text(encoding="utf-8")

    package_root = resources.files("outlook_mail_extractor").joinpath(
        "resources", "config_samples"
    )
    resource = package_root.joinpath(*relative_path.parts)
    return resource.read_text(encoding="utf-8")


def ensure_config_samples(config_dir: Path, project_root: Path | None = None) -> int:
    """Ensure packaged `*.yaml.sample` files exist under user config dir."""
    copied = 0
    for relative_path in _SAMPLE_FILES:
        target = config_dir / relative_path
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _read_template_text(relative_path, project_root=project_root),
            encoding="utf-8",
        )
        copied += 1
    return copied


def all_configs_initialized(config_dir: Path) -> bool:
    """Return whether all required runtime YAML files already exist."""
    for relative_path in _SAMPLE_FILES:
        if not (config_dir / relative_path.with_suffix("")).exists():
            return False
    return True


def initialize_configs(
    config_dir: Path, project_root: Path | None = None
) -> tuple[int, int]:
    """Copy packaged templates to runtime config files when missing."""
    ensure_config_samples(config_dir, project_root=project_root)

    copied = 0
    skipped = 0
    for relative_path in _SAMPLE_FILES:
        sample_path = config_dir / relative_path
        yaml_path = config_dir / relative_path.with_suffix("")
        if yaml_path.exists():
            skipped += 1
            continue
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        yaml_path.write_text(sample_path.read_text(encoding="utf-8"), encoding="utf-8")
        copied += 1
    return copied, skipped
