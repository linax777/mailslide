"""Plugin base classes"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeVar

from ..models import (
    DomainError,
    EmailDTO,
    InfrastructureError,
    MailActionPort,
    PluginExecutionResult,
    PluginExecutionStatus,
)


@dataclass
class PluginConfig:
    """Plugin configuration"""

    enabled: bool = True
    system_prompt: str = ""
    response_format: str = "json"
    override_prompt: str | None = None
    response_json_format: dict[str, str] | None = None


class PluginCapability(str, Enum):
    """Capability flags that drive orchestrator dispatch rules."""

    REQUIRES_LLM = "requires_llm"
    CAN_SKIP_BY_RESPONSE = "can_skip_by_response"
    MOVES_MESSAGE = "moves_message"


class BasePlugin(ABC):
    """Base class for all plugins"""

    name: str = ""
    default_system_prompt: str = ""
    capabilities: set[PluginCapability] = set()

    def __init__(self, config: dict | None = None):
        self.config = self._load_config(config or {})

    def _parse_response(self, response: str) -> dict:
        """Parse JSON from LLM response"""
        clean = re.sub(r"^```json\s*", "", response.strip())
        clean = re.sub(r"\s*```$", "", clean)
        clean = clean.strip()
        json_match = re.search(r"\{[^}]+\}", clean, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def _load_config(self, config: dict) -> PluginConfig:
        return PluginConfig(
            enabled=config.get("enabled", True),
            system_prompt=config.get("system_prompt", self.default_system_prompt),
            response_format=config.get("response_format", "json"),
            override_prompt=config.get("override_prompt"),
            response_json_format=config.get("response_json_format"),
        )

    def _wrap_unexpected_error(
        self, context: str, error: Exception
    ) -> InfrastructureError:
        """Create a consistent infrastructure-level error for unknown failures."""
        return InfrastructureError(
            f"{self.name or self.__class__.__name__} {context}: {error}"
        )

    def _is_expected_error(self, error: Exception) -> bool:
        """Check if an error is already an application-level typed error."""
        return isinstance(error, (DomainError, InfrastructureError))

    @property
    def effective_prompt(self) -> str:
        """Get the effective system prompt (override takes priority)"""
        return self.config.override_prompt or self.config.system_prompt

    def build_effective_prompt(self) -> str:
        """
        Build the effective system prompt including JSON format examples.

        If response_json_format is defined in config, append the format examples
        to the system prompt automatically.
        """
        base_prompt = self.effective_prompt
        json_format = self.config.response_json_format

        if not json_format:
            return base_prompt

        format_examples = []
        if "create_true" in json_format:
            format_examples.append(f"需要建立約會時：\n{json_format['create_true']}")
        if "create_false" in json_format:
            format_examples.append(f"不需要建立約會時：\n{json_format['create_false']}")
        if "has_category" in json_format:
            format_examples.append(f"需要分類時：\n{json_format['has_category']}")
        if "no_category" in json_format:
            format_examples.append(f"不需要分類時：\n{json_format['no_category']}")
        if "move" in json_format:
            format_examples.append(f"需要移動時：\n{json_format['move']}")
        if "no_move" in json_format:
            format_examples.append(f"不需要移動時：\n{json_format['no_move']}")

        if format_examples:
            return f"{base_prompt}\n\n{' '.join(format_examples)}"

        return base_prompt

    def supports(self, capability: PluginCapability) -> bool:
        """Return True when plugin declares the given capability."""
        return capability in self.capabilities

    def requires_llm(self) -> bool:
        """Return True when plugin should be executed after LLM call."""
        return self.supports(PluginCapability.REQUIRES_LLM) or bool(
            self.build_effective_prompt()
        )

    def should_skip_by_response(
        self,
        llm_response: str,
    ) -> PluginExecutionResult | None:
        """Optionally short-circuit execution based on LLM response."""
        del llm_response
        return None

    def begin_job(self, context: dict | None = None) -> None:
        """Hook called once before processing a job."""
        del context

    def end_job(self) -> PluginExecutionResult | None:
        """Hook called once after processing a job for optional flush logic."""
        return None

    def success_result(
        self,
        message: str = "Success",
        code: str = "",
        details: dict | None = None,
    ) -> PluginExecutionResult:
        """Build a success plugin execution result."""
        return PluginExecutionResult(
            status=PluginExecutionStatus.SUCCESS,
            code=code,
            message=message,
            details=details or {},
        )

    def skipped_result(
        self,
        message: str = "Skipped",
        code: str = "",
        details: dict | None = None,
    ) -> PluginExecutionResult:
        """Build a skipped plugin execution result."""
        return PluginExecutionResult(
            status=PluginExecutionStatus.SKIPPED,
            code=code,
            message=message,
            details=details or {},
        )

    def failed_result(
        self,
        message: str = "Failed",
        code: str = "",
        details: dict | None = None,
    ) -> PluginExecutionResult:
        """Build a failed plugin execution result."""
        return PluginExecutionResult(
            status=PluginExecutionStatus.FAILED,
            code=code,
            message=message,
            details=details or {},
        )

    def retriable_failed_result(
        self,
        message: str,
        code: str = "",
        details: dict | None = None,
    ) -> PluginExecutionResult:
        """Build a retriable failed plugin execution result."""
        return PluginExecutionResult(
            status=PluginExecutionStatus.RETRIABLE_FAILED,
            code=code,
            message=message,
            details=details or {},
        )

    @abstractmethod
    async def execute(
        self,
        email_data: EmailDTO,
        llm_response: str,
        action_port: MailActionPort,
    ) -> bool | PluginExecutionResult:
        """
        Execute the plugin action.

        Args:
            email_data: Extracted pure email data
            llm_response: LLM response text
            action_port: Side-effect action port for mail operations

        Returns:
            bool (legacy) or PluginExecutionResult
        """
        pass


_plugin_registry: dict[str, type[BasePlugin]] = {}
TPlugin = TypeVar("TPlugin", bound=BasePlugin)


def register_plugin(cls: type[TPlugin]) -> type[TPlugin]:
    """Register a plugin class"""
    _plugin_registry[cls.name] = cls
    return cls


def get_plugin(name: str, config: dict | None = None) -> BasePlugin | None:
    """Get a plugin instance by name"""
    cls = _plugin_registry.get(name)
    if cls:
        return cls(config)
    return None


def list_plugins() -> list[str]:
    """List all registered plugin names"""
    return list(_plugin_registry.keys())


def load_plugin_configs(
    plugins_dir: Path | str = "config/plugins",
) -> dict[str, dict]:
    """Load all plugin configs from directory"""
    import yaml

    configs: dict[str, dict] = {}
    plugins_path = Path(plugins_dir)

    if not plugins_path.exists():
        return configs

    for yaml_file in plugins_path.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue
        plugin_name = yaml_file.stem
        with open(yaml_file, "r", encoding="utf-8") as f:
            configs[plugin_name] = yaml.safe_load(f) or {}

    return configs
