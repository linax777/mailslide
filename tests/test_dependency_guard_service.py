from importlib.metadata import PackageNotFoundError

import pytest

from outlook_mail_extractor.contracts.dependency_guard import DEPENDENCY_GUARD_REASON
from outlook_mail_extractor.models import DependencyGuardError
from outlook_mail_extractor.services.dependency_guard import DependencyGuardService


def test_dependency_guard_allows_compatible_httpx_version() -> None:
    service = DependencyGuardService(
        policy_reader=lambda: "<1",
        version_reader=lambda _name: "0.28.1",
    )

    service.ensure_llm_runtime_compatible()


def test_dependency_guard_blocks_boundary_httpx_version() -> None:
    service = DependencyGuardService(
        policy_reader=lambda: "<1",
        version_reader=lambda _name: "1.0.0",
    )

    with pytest.raises(DependencyGuardError) as exc_info:
        service.ensure_llm_runtime_compatible()

    assert exc_info.value.reason == DEPENDENCY_GUARD_REASON
    assert "httpx" in str(exc_info.value)


def test_dependency_guard_maps_policy_parse_failure_to_guard_contract() -> None:
    def _raise_policy_error() -> str:
        raise ValueError("metadata parse failed")

    service = DependencyGuardService(
        policy_reader=_raise_policy_error,
        version_reader=lambda _name: "0.28.1",
    )

    with pytest.raises(DependencyGuardError) as exc_info:
        service.ensure_llm_runtime_compatible()

    assert exc_info.value.reason == DEPENDENCY_GUARD_REASON
    assert "metadata" in str(exc_info.value)


def test_dependency_guard_reports_missing_httpx_dependency() -> None:
    def _missing_dependency(_name: str) -> str:
        raise PackageNotFoundError("httpx")

    service = DependencyGuardService(
        policy_reader=lambda: "<1",
        version_reader=_missing_dependency,
    )

    with pytest.raises(DependencyGuardError) as exc_info:
        service.ensure_llm_runtime_compatible()

    assert exc_info.value.reason == DEPENDENCY_GUARD_REASON
    assert "httpx" in str(exc_info.value).lower()


def test_dependency_guard_maps_generic_version_reader_failure() -> None:
    def _version_reader_fails(_name: str) -> str:
        raise RuntimeError("version read failed")

    service = DependencyGuardService(
        policy_reader=lambda: "<1",
        version_reader=_version_reader_fails,
    )

    with pytest.raises(DependencyGuardError) as exc_info:
        service.ensure_llm_runtime_compatible()

    assert exc_info.value.reason == DEPENDENCY_GUARD_REASON
    assert "version" in str(exc_info.value).lower()


def test_dependency_guard_maps_invalid_installed_version_string() -> None:
    service = DependencyGuardService(
        policy_reader=lambda: "<1",
        version_reader=lambda _name: "not-a-version",
    )

    with pytest.raises(DependencyGuardError) as exc_info:
        service.ensure_llm_runtime_compatible()

    assert exc_info.value.reason == DEPENDENCY_GUARD_REASON
    assert "httpx" in str(exc_info.value).lower()
