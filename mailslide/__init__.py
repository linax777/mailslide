"""mailslide compatibility package.

This package re-exports the public API from ``outlook_mail_extractor``
during the import-path migration period.
"""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version as dist_version

try:
    __version__ = dist_version("mailslide")
except PackageNotFoundError:
    __version__ = "0.4.2"


def __getattr__(name: str):
    if name == "__version__":
        return __version__
    legacy = import_module("outlook_mail_extractor")
    return getattr(legacy, name)


def __dir__() -> list[str]:
    legacy = import_module("outlook_mail_extractor")
    names = set(globals())
    names.update(getattr(legacy, "__all__", []))
    names.add("__version__")
    return sorted(names)


__all__ = [
    "OutlookConnectionError",
    "FolderNotFoundError",
    "LLMError",
    "AppError",
    "DomainError",
    "InfrastructureError",
    "UserVisibleError",
    "DependencyGuardError",
    "OutlookClient",
    "EmailProcessor",
    "LLMClient",
    "LLMConfig",
    "check_llm_config",
    "load_llm_config",
    "load_config",
    "validate_config",
    "CheckStatus",
    "ConfigStatus",
    "OutlookStatus",
    "SystemStatus",
    "LLMConfigStatus",
    "PluginResult",
    "AttachmentDescriptor",
    "EmailDTO",
    "MailActionPort",
    "EmailAnalysisResult",
    "process_config_file",
    "clean_content",
    "clean_invisible_chars",
    "parse_tables",
    "LoggerManager",
    "LogSessionManager",
    "get_logger",
    "RuntimePaths",
    "RuntimeContext",
    "LoggerManagerProtocol",
    "build_runtime_paths",
    "get_runtime_context",
    "__version__",
]
