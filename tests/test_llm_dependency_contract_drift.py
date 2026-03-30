import importlib.util
from pathlib import Path
import types

import pytest


def _load_drift_script_module() -> types.ModuleType:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "check_llm_dependency_contract.py"
    )
    spec = importlib.util.spec_from_file_location(
        "check_llm_dependency_contract",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load check_llm_dependency_contract.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_llm_dependency_contract_check_passes_when_policies_match(
    tmp_path: Path,
) -> None:
    module = _load_drift_script_module()
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "mailslide"
version = "0.0.0"

[project.optional-dependencies]
llm = [
    "httpx<1",
]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    policy = module.validate_llm_dependency_contract(pyproject_path)
    assert policy == "<1"


def test_llm_dependency_contract_check_handles_additional_markers(
    tmp_path: Path,
) -> None:
    module = _load_drift_script_module()
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "mailslide"
version = "0.0.0"

[project.optional-dependencies]
llm = [
    "httpx<1; python_version >= '3.13'",
]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    policy = module.validate_llm_dependency_contract(pyproject_path)
    assert policy == "<1"


def test_llm_dependency_contract_check_fails_on_parser_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_drift_script_module()
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "mailslide"
version = "0.0.0"

[project.optional-dependencies]
llm = [
    "httpx<1",
]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module,
        "extract_httpx_llm_policy_from_requirement_entries",
        lambda _entries: "<2",
    )

    with pytest.raises(ValueError, match="drift"):
        module.validate_llm_dependency_contract(pyproject_path)


def test_llm_dependency_contract_check_fails_when_llm_policy_missing(
    tmp_path: Path,
) -> None:
    module = _load_drift_script_module()
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "mailslide"
version = "0.0.0"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="optional-dependencies.llm"):
        module.validate_llm_dependency_contract(pyproject_path)


def test_release_workflow_runs_llm_dependency_contract_check() -> None:
    workflow_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "publish-pypi.yml"
    )
    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "Check LLM dependency contract drift" in workflow_text
    assert "uv run python scripts/check_llm_dependency_contract.py" in workflow_text
