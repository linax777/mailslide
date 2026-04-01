"""Plugin system for mailslide."""

import importlib

from .base import (
    BasePlugin,
    PluginCapability,
    PluginConfig,
    get_plugin,
    list_plugins,
    load_plugin_configs,
    register_plugin,
)
from ..parser import clean_invisible_chars

# Import all plugins to register them
from . import (  # noqa: F401, E402
    calendar,
    category,
    download_attachments,
    event_table,
    move,
    summary_file,
    write_file,
)


def load_plugin_modules(module_paths: list[str]) -> list[str]:
    """Dynamically import additional plugin modules and return loaded names."""
    loaded_modules: list[str] = []
    for module_path in module_paths:
        module_name = str(module_path).strip()
        if not module_name:
            continue
        importlib.import_module(module_name)
        loaded_modules.append(module_name)
    return loaded_modules


__all__ = [
    "BasePlugin",
    "PluginCapability",
    "PluginConfig",
    "clean_invisible_chars",
    "get_plugin",
    "list_plugins",
    "load_plugin_configs",
    "load_plugin_modules",
    "register_plugin",
]
