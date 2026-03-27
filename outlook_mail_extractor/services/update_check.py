"""PyPI update check service."""

from dataclasses import dataclass

import httpx
from packaging.version import InvalidVersion, Version


PYPI_PROJECT_URL = "https://pypi.org/pypi/mailslide/json"


@dataclass(frozen=True)
class UpdateCheckResult:
    """Result of checking the latest release on PyPI."""

    current_version: str
    latest_version: str | None
    has_update: bool
    error: str | None = None


class UpdateCheckService:
    """Check whether a newer stable version is available on PyPI."""

    def __init__(
        self,
        current_version: str,
        project_url: str = PYPI_PROJECT_URL,
        timeout_seconds: float = 8.0,
    ):
        self._current_version = current_version
        self._project_url = project_url
        self._timeout_seconds = timeout_seconds

    def check(self) -> UpdateCheckResult:
        try:
            response = httpx.get(self._project_url, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            return UpdateCheckResult(
                current_version=self._current_version,
                latest_version=None,
                has_update=False,
                error=str(e),
            )

        latest_version = self._extract_latest_version(payload)
        if not latest_version:
            return UpdateCheckResult(
                current_version=self._current_version,
                latest_version=None,
                has_update=False,
                error="Invalid PyPI response: missing info.version",
            )

        try:
            has_update = Version(latest_version) > Version(self._current_version)
        except InvalidVersion as e:
            return UpdateCheckResult(
                current_version=self._current_version,
                latest_version=latest_version,
                has_update=False,
                error=f"Invalid version format: {e}",
            )

        return UpdateCheckResult(
            current_version=self._current_version,
            latest_version=latest_version,
            has_update=has_update,
            error=None,
        )

    @staticmethod
    def _extract_latest_version(payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None
        info = payload.get("info")
        if not isinstance(info, dict):
            return None
        version = info.get("version")
        if not isinstance(version, str):
            return None
        normalized = version.strip()
        return normalized or None
