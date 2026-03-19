"""Plugin system for Outlook Mail Extractor"""

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
from . import category, calendar, event_table, move, write_file  # noqa: F401, E402

__all__ = [
    "BasePlugin",
    "PluginCapability",
    "PluginConfig",
    "clean_invisible_chars",
    "get_plugin",
    "list_plugins",
    "load_plugin_configs",
    "register_plugin",
]
