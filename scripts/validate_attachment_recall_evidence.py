"""Validate RC attachment-recall evidence artifact and gate metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tomllib

MIN_LABELED_DOWNLOADABLE_COUNT = 200
MIN_COMPLETENESS_RATIO = 0.98

_METRICS_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_REQUIRED_KEYS = (
    "sample_protocol_version",
    "label_set_version",
    "labeled_downloadable_count",
    "saved_downloadable_count",
    "completeness_ratio",
    "gate_verdict",
)


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


def resolve_report_path(version: str, reports_root: Path) -> Path | None:
    """Return required report path for RC versions, otherwise ``None``."""
    normalized_version = _normalize_version(version)
    match = re.fullmatch(r"(?P<base>\d+\.\d+\.\d+)rc(?P<rc>\d+)", normalized_version)
    if not match:
        return None

    report_name = f"{match.group('base')}-rc{match.group('rc')}.md"
    return reports_root / report_name


def _extract_metrics_payload(report_content: str) -> dict[str, object] | None:
    match = _METRICS_JSON_BLOCK.search(report_content)
    if not match:
        return None

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def _load_baseline_versions(baseline_path: Path) -> tuple[str, str] | None:
    if not baseline_path.exists():
        return None

    try:
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    protocol = payload.get("sample_protocol_version")
    label_set = payload.get("label_set_version")
    if not isinstance(protocol, str) or not isinstance(label_set, str):
        return None
    return protocol, label_set


def validate_attachment_recall_report(
    report_path: Path,
    *,
    baseline_path: Path,
) -> list[str]:
    """Return validation errors for one attachment recall report."""
    if not report_path.exists():
        return [f"missing required report file: {report_path}"]

    report_content = report_path.read_text(encoding="utf-8")
    metrics_payload = _extract_metrics_payload(report_content)
    if metrics_payload is None:
        return ["missing or invalid metrics JSON block"]

    errors: list[str] = []
    for key in _REQUIRED_KEYS:
        if key not in metrics_payload:
            errors.append(f"missing required metric key: {key}")

    if errors:
        return errors

    protocol_version = metrics_payload["sample_protocol_version"]
    label_set_version = metrics_payload["label_set_version"]
    labeled_count = metrics_payload["labeled_downloadable_count"]
    saved_count = metrics_payload["saved_downloadable_count"]
    completeness_ratio = metrics_payload["completeness_ratio"]
    gate_verdict = metrics_payload["gate_verdict"]

    if not isinstance(protocol_version, str) or not protocol_version.strip():
        errors.append("sample_protocol_version must be non-empty string")
    if not isinstance(label_set_version, str) or not label_set_version.strip():
        errors.append("label_set_version must be non-empty string")
    if not isinstance(labeled_count, int) or labeled_count <= 0:
        errors.append("labeled_downloadable_count must be positive integer")
    if not isinstance(saved_count, int) or saved_count < 0:
        errors.append("saved_downloadable_count must be non-negative integer")
    if isinstance(saved_count, int) and isinstance(labeled_count, int):
        if saved_count > labeled_count:
            errors.append(
                "saved_downloadable_count cannot exceed labeled_downloadable_count"
            )

    if not isinstance(completeness_ratio, int | float):
        errors.append("completeness_ratio must be numeric")
    if not isinstance(gate_verdict, str) or gate_verdict not in {"pass", "fail"}:
        errors.append("gate_verdict must be either 'pass' or 'fail'")

    baseline_versions = _load_baseline_versions(baseline_path)
    if baseline_versions is None:
        errors.append(f"missing or invalid baseline file: {baseline_path}")
    else:
        baseline_protocol, baseline_label_set = baseline_versions
        if protocol_version != baseline_protocol:
            errors.append("sample_protocol_version does not match approved baseline")
        if label_set_version != baseline_label_set:
            errors.append("label_set_version does not match approved baseline")

    if isinstance(labeled_count, int):
        if labeled_count < MIN_LABELED_DOWNLOADABLE_COUNT:
            errors.append(
                "labeled_downloadable_count is below minimum required threshold"
            )

    if (
        isinstance(labeled_count, int)
        and labeled_count > 0
        and isinstance(saved_count, int)
        and isinstance(completeness_ratio, int | float)
    ):
        computed_ratio = saved_count / labeled_count
        if abs(completeness_ratio - computed_ratio) > 1e-6:
            errors.append(
                "completeness_ratio does not match saved_downloadable_count / labeled_downloadable_count"
            )

        expected_verdict = (
            "pass" if computed_ratio >= MIN_COMPLETENESS_RATIO else "fail"
        )
        if gate_verdict != expected_verdict:
            errors.append("gate_verdict does not match computed completeness threshold")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate RC attachment recall evidence"
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
        "--reports-root",
        type=Path,
        default=Path("docs/releases/attachment-recall"),
        help="Directory containing attachment recall report artifacts",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("docs/releases/attachment-recall/baseline.json"),
        help="Path to approved baseline versions file",
    )
    args = parser.parse_args()

    version = args.version or _read_project_version(args.pyproject)
    report_path = resolve_report_path(version, args.reports_root)
    if report_path is None:
        print(f"Attachment recall validation skipped for non-RC version: {version}")
        return 0

    errors = validate_attachment_recall_report(
        report_path,
        baseline_path=args.baseline,
    )
    if errors:
        print(f"Attachment recall validation failed for {report_path}:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Attachment recall validation passed: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
