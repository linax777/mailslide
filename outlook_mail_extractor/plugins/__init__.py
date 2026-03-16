"""Plugin system for Outlook Mail Extractor"""

from .base import (
    BasePlugin,
    PluginConfig,
    get_plugin,
    list_plugins,
    load_plugin_configs,
    register_plugin,
)
from ..parser import clean_invisible_chars

# Import all plugins to register them
from . import category, calendar, move, write_file  # noqa: F401, E402

__all__ = [
    "BasePlugin",
    "PluginConfig",
    "clean_invisible_chars",
    "get_plugin",
    "list_plugins",
    "load_plugin_configs",
    "register_plugin",
]
