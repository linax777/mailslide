import shutil
import subprocess
from pathlib import Path

import pytest


def _write_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _write_crlf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)


def test_update_version_script_updates_lockfile_without_group_ambiguity(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("pwsh is required for this test")

    repo_root = tmp_path
    scripts_dir = repo_root / "scripts"
    package_dir = repo_root / "outlook_mail_extractor"
    screens_dir = package_dir / "screens"

    scripts_dir.mkdir(parents=True, exist_ok=True)
    screens_dir.mkdir(parents=True, exist_ok=True)

    source_script = (
        Path(__file__).resolve().parents[1] / "scripts" / "update_version.ps1"
    )
    target_script = scripts_dir / "update_version.ps1"
    _write_lf(target_script, source_script.read_text(encoding="utf-8"))

    _write_lf(
        repo_root / "pyproject.toml",
        '[project]\nname = "mailslide"\nversion = "0.3.8"\n',
    )
    _write_lf(
        package_dir / "__init__.py",
        '__version__ = "0.3.8"\n',
    )
    _write_lf(
        screens_dir / "about.py",
        'class AboutScreen:\n    VERSION = "0.3.8"\n',
    )
    _write_lf(
        repo_root / "uv.lock",
        "[[package]]\n"
        'name = "mailslide"\n'
        'version = "0.3.8"\n'
        'source = { editable = "." }\n'
        "dependencies = [\n"
        '    { name = "loguru" },\n'
        "]\n",
    )

    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(target_script),
            "-Version",
            "0.3.9",
            "-SkipChangelog",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise AssertionError(
            f"update_version.ps1 failed: {completed.stdout}\n{completed.stderr}"
        )

    lock_text = (repo_root / "uv.lock").read_text(encoding="utf-8")
    assert (
        'name = "mailslide"\nversion = "0.3.9"\nsource = { editable = "." }'
        in lock_text
    )
    assert '$10.3.9"' not in lock_text


def test_update_version_script_supports_crlf_files(tmp_path: Path) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("pwsh is required for this test")

    repo_root = tmp_path
    scripts_dir = repo_root / "scripts"
    package_dir = repo_root / "outlook_mail_extractor"
    screens_dir = package_dir / "screens"

    scripts_dir.mkdir(parents=True, exist_ok=True)
    screens_dir.mkdir(parents=True, exist_ok=True)

    source_script = (
        Path(__file__).resolve().parents[1] / "scripts" / "update_version.ps1"
    )
    target_script = scripts_dir / "update_version.ps1"
    _write_lf(target_script, source_script.read_text(encoding="utf-8"))

    _write_crlf(
        repo_root / "pyproject.toml",
        '[project]\nname = "mailslide"\nversion = "0.3.8"\n',
    )
    _write_crlf(
        package_dir / "__init__.py",
        '__version__ = "0.3.8"\n',
    )
    _write_crlf(
        screens_dir / "about.py",
        'class AboutScreen:\n    VERSION = "0.3.8"\n',
    )
    _write_crlf(
        repo_root / "uv.lock",
        "[[package]]\n"
        'name = "mailslide"\n'
        'version = "0.3.8"\n'
        'source = { editable = "." }\n',
    )

    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(target_script),
            "-Version",
            "0.3.9",
            "-SkipChangelog",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise AssertionError(
            f"update_version.ps1 failed: {completed.stdout}\n{completed.stderr}"
        )

    pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    init_text = (package_dir / "__init__.py").read_text(encoding="utf-8")
    about_text = (screens_dir / "about.py").read_text(encoding="utf-8")

    assert 'version = "0.3.9"' in pyproject_text
    assert '__version__ = "0.3.9"' in init_text
    assert 'VERSION = "0.3.9"' in about_text
