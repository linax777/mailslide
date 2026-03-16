"""Data models - System status and LLM related"""

from dataclasses import dataclass, field
from enum import Enum


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


class LLMProvider(str, Enum):
    """LLM provider type"""

    OPENAI = "openai"
    LLAMA_CPP = "llama.cpp"


@dataclass
class LLMConfigStatus:
    """LLM configuration status"""

    status: CheckStatus
    message: str
    provider: str = ""
    model: str = ""


@dataclass
class PluginResult:
    """Result of plugin execution"""

    plugin_name: str
    success: bool
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
