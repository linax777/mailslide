"""Validate RC evidence artifact presence and schema tokens."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import tomllib


SUCCESS_TOKEN = "dependency_guard_passed"
FAILURE_TOKEN = "dependency_guard_failed"

REQUIRED_FIELD_LABELS = [
    "Environment",
    "Install Command",
    "Job Config Marker",
    "Pass/Fail Output Snippet",
    "Timestamp",
]

UNFILLED_TEMPLATE_PATTERNS: list[tuple[str, str]] = [
    ("template title", r"(?m)^# RC Evidence Template: <version>-rcN\s*$"),
    ("OS", r"(?m)^- OS:\s*$"),
    ("Python", r"(?m)^- Python:\s*$"),
    ("Tooling", r"(?m)^- Tooling \(`uv --version`\):\s*$"),
    ("LLM-enabled job marker", r"(?m)^- LLM-enabled job marker:\s*$"),
    ("Non-LLM baseline marker", r"(?m)^- Non-LLM baseline marker:\s*$"),
    ("Timestamp", r"(?m)^- UTC:\s*$"),
    (
        "Local source-mode sanity run status",
        r"(?m)^- Local source-mode sanity run status:\s*$",
    ),
    ("Reviewer", r"(?m)^- Reviewer:\s*$"),
]


def _read_project_version(pyproject_path: Path) -> str:
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    if not isinstance(project, dict):
        raise ValueError("invalid pyproject format")
    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("project.version is missing")
    return version.strip()


def _normalize_version(raw_version: str) -> str:
    return raw_version.removeprefix("v")


def resolve_evidence_path(version: str, evidence_root: Path) -> Path | None:
    """Return required evidence path for RC versions, otherwise ``None``."""
    normalized_version = _normalize_version(version)
    match = re.fullmatch(r"(?P<base>\d+\.\d+\.\d+)rc(?P<rc>\d+)", normalized_version)
    if not match:
        return None

    evidence_name = f"{match.group('base')}-rc{match.group('rc')}.md"
    return evidence_root / evidence_name


def validate_rc_evidence_file(evidence_path: Path) -> list[str]:
    """Return validation errors for one RC evidence artifact."""
    if not evidence_path.exists():
        return [f"missing required evidence file: {evidence_path}"]

    content = evidence_path.read_text(encoding="utf-8")
    errors: list[str] = []
    for field in REQUIRED_FIELD_LABELS:
        if field not in content:
            errors.append(f"missing required field label: {field}")

    if SUCCESS_TOKEN not in content:
        errors.append(f"missing success token: {SUCCESS_TOKEN}")
    if FAILURE_TOKEN not in content:
        errors.append(f"missing failure token: {FAILURE_TOKEN}")

    for placeholder_label, placeholder_pattern in UNFILLED_TEMPLATE_PATTERNS:
        if re.search(placeholder_pattern, content):
            errors.append(
                f"contains unfilled template placeholder: {placeholder_label}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate RC dependency-guard evidence"
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Release version/tag (default: read from pyproject.toml)",
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("docs/releases/evidence"),
        help="Directory containing RC evidence artifacts",
    )
    args = parser.parse_args()

    version = args.version or _read_project_version(args.pyproject)
    evidence_path = resolve_evidence_path(version, args.evidence_root)
    if evidence_path is None:
        print(f"RC evidence validation skipped for non-RC version: {version}")
        return 0

    errors = validate_rc_evidence_file(evidence_path)
    if errors:
        print(f"RC evidence validation failed for {evidence_path}:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"RC evidence validation passed: {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
