"""mailslide - Organize emails in Outlook Classic."""

import os
from importlib.metadata import PackageNotFoundError, version as dist_version

from mailslide._compat import warn_legacy_import
from .config import load_config, validate_config
from .core import (
    EmailProcessor,
    FolderNotFoundError,
    OutlookClient,
    OutlookConnectionError,
    check_llm_config,
    process_config_file,
)
from .llm import LLMClient, LLMConfig, LLMError, load_llm_config
from .logger import LogSessionManager, LoggerManager, get_logger
from .models import (
    AttachmentDescriptor,
    AppError,
    CheckStatus,
    ConfigStatus,
    DependencyGuardError,
    DomainError,
    EmailDTO,
    EmailAnalysisResult,
    InfrastructureError,
    LLMConfigStatus,
    MailActionPort,
    OutlookStatus,
    PluginResult,
    SystemStatus,
    UserVisibleError,
)
from .parser import clean_content, clean_invisible_chars, parse_tables
from .runtime import (
    LoggerManagerProtocol,
    RuntimeContext,
    RuntimePaths,
    build_runtime_paths,
    get_runtime_context,
)

try:
    __version__ = dist_version("mailslide")
except PackageNotFoundError:
    __version__ = "0.4.2"

__all__ = [
    # Exceptions
    "OutlookConnectionError",
    "FolderNotFoundError",
    "LLMError",
    "AppError",
    "DomainError",
    "InfrastructureError",
    "UserVisibleError",
    "DependencyGuardError",
    # Core classes
    "OutlookClient",
    "EmailProcessor",
    # LLM
    "LLMClient",
    "LLMConfig",
    "check_llm_config",
    "load_llm_config",
    # Config
    "load_config",
    "validate_config",
    # Models
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
    # Utilities
    "process_config_file",
    "clean_content",
    "clean_invisible_chars",
    "parse_tables",
    # Logger
    "LoggerManager",
    "LogSessionManager",
    "get_logger",
    # Runtime
    "RuntimePaths",
    "RuntimeContext",
    "LoggerManagerProtocol",
    "build_runtime_paths",
    "get_runtime_context",
]

if os.environ.get("MAILSLIDE_IMPORT_WARNING") == "1":
    warn_legacy_import()
