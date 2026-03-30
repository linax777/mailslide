"""Validate LLM dependency-policy contract drift."""

from __future__ import annotations

import argparse
from pathlib import Path
import tomllib

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet

from outlook_mail_extractor.services.dependency_guard import (
    extract_httpx_llm_policy_from_requirement_entries,
)


def _read_llm_optional_dependencies(pyproject_path: Path) -> list[str]:
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    if not isinstance(project, dict):
        raise ValueError("invalid pyproject: [project] must be a table")

    optional_dependencies = project.get("optional-dependencies", {})
    if not isinstance(optional_dependencies, dict):
        raise ValueError("invalid pyproject: optional-dependencies must be a table")

    llm_dependencies = optional_dependencies.get("llm")
    if llm_dependencies is None:
        raise ValueError("missing optional-dependencies.llm")
    if not isinstance(llm_dependencies, list) or not all(
        isinstance(item, str) for item in llm_dependencies
    ):
        raise ValueError("optional-dependencies.llm must be a list[str]")

    return llm_dependencies


def _canonical_httpx_policy_from_llm_dependencies(llm_dependencies: list[str]) -> str:
    policy_fragments: list[str] = []
    for raw_requirement in llm_dependencies:
        try:
            requirement = Requirement(raw_requirement)
        except InvalidRequirement as e:
            raise ValueError(
                f"invalid llm dependency requirement: {raw_requirement}"
            ) from e

        if requirement.name.casefold() != "httpx":
            continue

        specifier = str(requirement.specifier).strip()
        if not specifier:
            raise ValueError("llm httpx dependency must include a version specifier")
        policy_fragments.append(specifier)

    if not policy_fragments:
        raise ValueError("optional-dependencies.llm must define httpx policy")

    return ",".join(policy_fragments)


def _build_runtime_metadata_requirements(llm_dependencies: list[str]) -> list[str]:
    metadata_requirements: list[str] = []
    for raw_requirement in llm_dependencies:
        requirement = Requirement(raw_requirement)
        marker = str(requirement.marker).strip() if requirement.marker else ""
        marker_with_extra = (
            f"({marker}) and (extra == 'llm')" if marker else "extra == 'llm'"
        )
        metadata_requirements.append(
            f"{requirement.name}{requirement.specifier}; {marker_with_extra}"
        )
    return metadata_requirements


def validate_llm_dependency_contract(pyproject_path: Path) -> str:
    """Validate that runtime parser policy equals canonical metadata policy."""
    llm_dependencies = _read_llm_optional_dependencies(pyproject_path)
    canonical_policy = _canonical_httpx_policy_from_llm_dependencies(llm_dependencies)
    runtime_requirement_entries = _build_runtime_metadata_requirements(llm_dependencies)
    runtime_policy = extract_httpx_llm_policy_from_requirement_entries(
        runtime_requirement_entries
    )

    normalized_canonical = str(SpecifierSet(canonical_policy))
    normalized_runtime = str(SpecifierSet(runtime_policy))
    if normalized_canonical != normalized_runtime:
        raise ValueError(
            "runtime dependency parser drift detected: "
            f"canonical={normalized_canonical}, runtime={normalized_runtime}"
        )

    return normalized_canonical


def main() -> int:
    parser = argparse.ArgumentParser(description="Check LLM dependency contract drift")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml",
    )
    args = parser.parse_args()

    try:
        policy = validate_llm_dependency_contract(args.pyproject)
    except Exception as e:
        print(f"LLM dependency contract check failed: {e}")
        return 1

    print(f"LLM dependency contract check passed: httpx{policy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
