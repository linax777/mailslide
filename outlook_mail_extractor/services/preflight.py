"""Preflight validation service shared by CLI/TUI."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from ..core import FolderNotFoundError, OutlookClient


class OutlookClientProtocol(Protocol):
    """Minimal Outlook client interface required by preflight checks."""

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def list_accounts(self) -> list[str]: ...

    def get_folder(
        self,
        account: str,
        folder_path: str,
        create_if_missing: bool = False,
    ): ...


@dataclass
class PreflightCheckResult:
    """Preflight validation output."""

    account_count: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        """Return True when preflight has no issues."""
        return not self.issues


class PreflightCheckService:
    """Validate enabled jobs against current Outlook state."""

    def __init__(
        self,
        client_factory: Callable[[], OutlookClientProtocol] = OutlookClient,
    ):
        self._client_factory = client_factory

    def validate_enabled_jobs_with_client(
        self,
        client: OutlookClientProtocol,
        config: dict,
    ) -> list[str]:
        """Validate account/source settings for enabled jobs."""
        issues: list[str] = []
        available_accounts = set(client.list_accounts())

        for job in config.get("jobs", []):
            if job.get("enable", True) is False:
                continue

            job_name = job.get("name", "Unnamed Job")
            account = job.get("account", "")
            source = job.get("source", "")

            if account not in available_accounts:
                issues.append(f"{job_name}: Account not found: {account}")
                continue

            try:
                client.get_folder(account, source)
            except FolderNotFoundError as e:
                issues.append(f"{job_name}: {e}")

        return issues

    def run(self, config: dict) -> PreflightCheckResult:
        """Run preflight checks with a managed Outlook client lifecycle."""
        enabled_jobs = [
            job for job in config.get("jobs", []) if job.get("enable", True)
        ]

        client = self._client_factory()
        try:
            client.connect()
            accounts = client.list_accounts()
            issues: list[str] = []
            if enabled_jobs:
                issues = self.validate_enabled_jobs_with_client(
                    client,
                    {"jobs": enabled_jobs},
                )
            return PreflightCheckResult(account_count=len(accounts), issues=issues)
        finally:
            client.disconnect()
