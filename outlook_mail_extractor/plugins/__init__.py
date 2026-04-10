"""Plugin system for mailslide."""

from .base import (
    BasePlugin,
    PluginCapability,
    PluginConfig,
    get_plugin,
    list_plugins,
    load_plugin_configs,
    register_plugin,
)
from .loader import load_builtin_plugins, load_external_plugin_modules
from ..parser import clean_invisible_chars

load_builtin_plugins()


def load_plugin_modules(module_paths: list[str]) -> list[str]:
    """Dynamically import additional plugin modules and return loaded names."""
    module_names: list[str] = []
    for module_path in module_paths:
        module_name = str(module_path).strip()
        if not module_name:
            continue
        module_names.append(module_name)
    return load_external_plugin_modules(module_names)


__all__ = [
    "BasePlugin",
    "PluginCapability",
    "PluginConfig",
    "clean_invisible_chars",
    "get_plugin",
    "list_plugins",
    "load_builtin_plugins",
    "load_plugin_configs",
    "load_plugin_modules",
    "register_plugin",
]
