"""Data models - System status and LLM related"""

from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class AppError(Exception):
    """Base class for all application-level exceptions."""


class DomainError(AppError):
    """Business/domain rule violation or invalid domain state."""


class InfrastructureError(AppError):
    """External dependency failure (Outlook, filesystem, network, etc.)."""


class UserVisibleError(AppError):
    """Expected error that can be shown to end users as-is."""


class CheckStatus(str, Enum):
    """Check status enum"""

    OK = "ok"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class ConfigStatus:
    """Config file check status"""

    status: CheckStatus
    message: str
    path: str = "config/config.yaml"


@dataclass
class OutlookStatus:
    """Outlook connection status"""

    status: CheckStatus
    message: str
    account_count: int = 0


@dataclass
class SystemStatus:
    """Overall system status"""

    config: ConfigStatus
    outlook: OutlookStatus

    @property
    def is_all_ok(self) -> bool:
        """Check if all items are OK"""
        return (
            self.config.status == CheckStatus.OK
            and self.outlook.status == CheckStatus.OK
        )


@dataclass
class LLMConfigStatus:
    """LLM configuration status"""

    status: CheckStatus
    message: str
    model: str = ""


class PluginExecutionStatus(str, Enum):
    """Standardized plugin execution status."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    RETRIABLE_FAILED = "retriable_failed"


@dataclass
class EmailDTO:
    """Pure email data used across domain/application layers."""

    subject: str
    sender: str
    received: str
    body: str
    tables: list[list[Any]]


class MailActionPort(Protocol):
    """Action interface for mail side effects decoupled from COM types."""

    def move_to_folder(self, folder_name: str, create_if_missing: bool = True) -> None:
        """Move current mail item to a folder under current account."""

    def add_categories(self, categories: list[str]) -> None:
        """Append categories to current mail item and persist changes."""

    def create_appointment(
        self,
        subject: str,
        start: datetime,
        end: datetime,
        location: str = "",
        body: str = "",
        recipients: list[str] | None = None,
    ) -> None:
        """Create a calendar appointment under current account."""


@dataclass
class PluginExecutionResult:
    """Structured execution result returned by plugins."""

    status: PluginExecutionStatus
    code: str = ""
    message: str = ""
    details: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Return True when plugin execution is successful."""
        return self.status == PluginExecutionStatus.SUCCESS


@dataclass
class PluginResult:
    """Result of plugin execution"""

    plugin_name: str
    success: bool
    status: PluginExecutionStatus = PluginExecutionStatus.SUCCESS
    code: str = ""
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class EmailAnalysisResult:
    """Result of email LLM analysis"""

    email_subject: str
    llm_response: str
    plugin_results: list[PluginResult] = field(default_factory=list)
    success: bool = True
    error_message: str = ""
