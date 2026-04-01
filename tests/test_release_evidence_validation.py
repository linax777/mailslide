import importlib.util
from pathlib import Path
import types


def _load_evidence_validator_module() -> types.ModuleType:
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "validate_rc_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("validate_rc_evidence", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load validate_rc_evidence.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_rc_evidence_file_accepts_required_fields_and_tokens(
    tmp_path: Path,
) -> None:
    module = _load_evidence_validator_module()
    evidence_path = tmp_path / "0.4.0-rc2.md"
    evidence_path.write_text(
        """
## Environment
## Install Command
## Job Config Marker
## Pass/Fail Output Snippet
## Timestamp
dependency_guard_passed
dependency_guard_failed
""".strip()
        + "\n",
        encoding="utf-8",
    )

    errors = module.validate_rc_evidence_file(evidence_path)
    assert errors == []


def test_validate_rc_evidence_file_rejects_missing_required_field(
    tmp_path: Path,
) -> None:
    module = _load_evidence_validator_module()
    evidence_path = tmp_path / "0.4.0-rc2.md"
    evidence_path.write_text(
        """
## Environment
## Install Command
## Job Config Marker
## Timestamp
dependency_guard_passed
dependency_guard_failed
""".strip()
        + "\n",
        encoding="utf-8",
    )

    errors = module.validate_rc_evidence_file(evidence_path)
    assert any("Pass/Fail Output Snippet" in error for error in errors)


def test_validate_rc_evidence_file_rejects_missing_failure_token(
    tmp_path: Path,
) -> None:
    module = _load_evidence_validator_module()
    evidence_path = tmp_path / "0.4.0-rc2.md"
    evidence_path.write_text(
        """
## Environment
## Install Command
## Job Config Marker
## Pass/Fail Output Snippet
## Timestamp
dependency_guard_passed
""".strip()
        + "\n",
        encoding="utf-8",
    )

    errors = module.validate_rc_evidence_file(evidence_path)
    assert any("dependency_guard_failed" in error for error in errors)


def test_validate_rc_evidence_file_rejects_missing_success_token(
    tmp_path: Path,
) -> None:
    module = _load_evidence_validator_module()
    evidence_path = tmp_path / "0.4.0-rc2.md"
    evidence_path.write_text(
        """
## Environment
## Install Command
## Job Config Marker
## Pass/Fail Output Snippet
## Timestamp
dependency_guard_failed
""".strip()
        + "\n",
        encoding="utf-8",
    )

    errors = module.validate_rc_evidence_file(evidence_path)
    assert any("dependency_guard_passed" in error for error in errors)


def test_resolve_evidence_path_supports_v_prefixed_rc_tag(tmp_path: Path) -> None:
    module = _load_evidence_validator_module()
    evidence_path = module.resolve_evidence_path("v0.4.0rc2", tmp_path)
    assert evidence_path == tmp_path / "0.4.0-rc2.md"


def test_resolve_evidence_path_skips_non_rc_versions(tmp_path: Path) -> None:
    module = _load_evidence_validator_module()
    evidence_path = module.resolve_evidence_path("v0.4.0", tmp_path)
    assert evidence_path is None


def test_validate_rc_evidence_file_rejects_missing_file(tmp_path: Path) -> None:
    module = _load_evidence_validator_module()
    errors = module.validate_rc_evidence_file(tmp_path / "0.4.0-rc2.md")
    assert any("missing required evidence file" in error for error in errors)


def test_validate_rc_evidence_file_rejects_unfilled_template_placeholders(
    tmp_path: Path,
) -> None:
    module = _load_evidence_validator_module()
    evidence_path = tmp_path / "0.4.1-rc2.md"
    evidence_path.write_text(
        """
# RC Evidence Template: <version>-rcN

## Environment

- OS:
- Python:
- Tooling (`uv --version`):

## Install Command

## Job Config Marker

- LLM-enabled job marker:
- Non-LLM baseline marker:

## Pass/Fail Output Snippet

dependency_guard_passed
dependency_guard_failed

## Timestamp

- UTC:

## Notes

- Local source-mode sanity run status:
- Reviewer:
""".strip()
        + "\n",
        encoding="utf-8",
    )

    errors = module.validate_rc_evidence_file(evidence_path)
    assert any("contains unfilled template placeholder" in error for error in errors)


def test_publish_workflow_contains_rc_evidence_validation_gate() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "publish-pypi.yml"
    )
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "Validate RC evidence artifact" in workflow_text
    assert (
        'scripts/validate_rc_evidence.py --version "${{ github.ref_name }}"'
        in workflow_text
    )
