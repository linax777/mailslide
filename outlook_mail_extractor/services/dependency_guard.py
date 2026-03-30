"""Runtime dependency-guard checks for LLM-enabled execution."""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, requires, version

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from ..i18n import t
from ..models import DependencyGuardError


def extract_httpx_llm_policy_from_requirement_entries(
    requirement_entries: list[str],
) -> str:
    """Extract canonical ``httpx`` specifier for the ``llm`` extra contract."""
    if not requirement_entries:
        raise ValueError("missing package metadata requirements")

    env = {key: str(value) for key, value in default_environment().items()}
    env["extra"] = "llm"
    matched_specifiers: list[str] = []

    for raw_requirement in requirement_entries:
        try:
            requirement = Requirement(raw_requirement)
        except InvalidRequirement as e:
            raise ValueError(f"invalid requirement entry: {raw_requirement}") from e

        if requirement.name.casefold() != "httpx":
            continue

        marker = requirement.marker
        if marker is None or not marker.evaluate(env):
            continue

        specifier = str(requirement.specifier).strip()
        if not specifier:
            raise ValueError("httpx requirement for llm extra has no specifier")
        matched_specifiers.append(specifier)

    if not matched_specifiers:
        raise ValueError("httpx policy for llm extra is missing")

    return ",".join(matched_specifiers)


def _read_httpx_policy_from_package_metadata() -> str:
    requirements = requires("mailslide")
    if requirements is None:
        raise ValueError("missing package metadata requirements")
    return extract_httpx_llm_policy_from_requirement_entries(list(requirements))


def _read_installed_version(distribution_name: str) -> str:
    return version(distribution_name)


class DependencyGuardService:
    """Validate that runtime dependencies satisfy canonical LLM policy."""

    def __init__(
        self,
        policy_reader: Callable[[], str] = _read_httpx_policy_from_package_metadata,
        version_reader: Callable[[str], str] = _read_installed_version,
    ):
        self._policy_reader = policy_reader
        self._version_reader = version_reader

    def ensure_llm_runtime_compatible(self) -> None:
        """Raise ``DependencyGuardError`` when runtime dependency policy is violated."""
        try:
            policy_specifier = self._policy_reader().strip()
            if not policy_specifier:
                raise ValueError("empty policy specifier")
            policy = SpecifierSet(policy_specifier)
        except (InvalidSpecifier, ValueError, TypeError) as e:
            raise DependencyGuardError(
                t(
                    "dependency_guard.error.policy_unavailable",
                    error=e,
                )
            ) from e

        try:
            installed_httpx = self._version_reader("httpx")
        except PackageNotFoundError as e:
            raise DependencyGuardError(
                t(
                    "dependency_guard.error.httpx_missing",
                    policy=policy_specifier,
                )
            ) from e
        except Exception as e:
            raise DependencyGuardError(
                t(
                    "dependency_guard.error.version_read_failed",
                    error=e,
                )
            ) from e

        try:
            resolved_version = Version(installed_httpx)
        except InvalidVersion as e:
            raise DependencyGuardError(
                t(
                    "dependency_guard.error.httpx_version_invalid",
                    version=installed_httpx,
                    policy=policy_specifier,
                )
            ) from e

        if resolved_version not in policy:
            raise DependencyGuardError(
                t(
                    "dependency_guard.error.httpx_incompatible",
                    version=resolved_version,
                    policy=policy_specifier,
                )
            )
