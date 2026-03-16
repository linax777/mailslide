"""Plugin base classes"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from pathlib import Path as PathType


@dataclass
class PluginConfig:
    """Plugin configuration"""

    enabled: bool = True
    system_prompt: str = ""
    response_format: str = "json"
    override_prompt: str | None = None
    response_json_format: dict[str, str] | None = None


class BasePlugin(ABC):
    """Base class for all plugins"""

    name: str = ""
    default_system_prompt: str = ""

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

        if format_examples:
            return f"{base_prompt}\n\n{' '.join(format_examples)}"

        return base_prompt

    @abstractmethod
    async def execute(
        self,
        email_data: dict,
        llm_response: str,
        outlook_client,
    ) -> bool:
        """
        Execute the plugin action.

        Args:
            email_data: Extracted email data
            llm_response: LLM response text
            outlook_client: OutlookClient instance

        Returns:
            True if action was successful
        """
        pass


_plugin_registry: dict[str, type[BasePlugin]] = {}


def register_plugin(cls: type[BasePlugin]) -> type[BasePlugin]:
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
    plugins_dir: Any = "config/plugins",
) -> dict[str, dict]:
    """Load all plugin configs from directory"""
    from pathlib import Path

    import yaml

    configs = {}
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
