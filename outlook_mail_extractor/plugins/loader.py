"""Plugin module loading utilities."""

from __future__ import annotations

import importlib


_BUILTIN_MODULES = [
    "outlook_mail_extractor.plugins.category",
    "outlook_mail_extractor.plugins.calendar",
    "outlook_mail_extractor.plugins.move",
    "outlook_mail_extractor.plugins.write_file",
    "outlook_mail_extractor.plugins.download_attachments",
    "outlook_mail_extractor.plugins.event_table",
    "outlook_mail_extractor.plugins.summary_file",
]

_loaded = False


def load_builtin_plugins() -> None:
    """Load built-in plugins exactly once."""
    global _loaded
    if _loaded:
        return
    for module_name in _BUILTIN_MODULES:
        importlib.import_module(module_name)
    _loaded = True


def load_external_plugin_modules(module_names: list[str]) -> list[str]:
    """Load external plugin modules and return loaded module names."""
    loaded_modules: list[str] = []
    for module_name in module_names:
        importlib.import_module(module_name)
        loaded_modules.append(module_name)
    return loaded_modules
