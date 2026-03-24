"""Outlook Mail Extractor - Read emails from Outlook Classic"""

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
    AppError,
    CheckStatus,
    ConfigStatus,
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

__version__ = "0.2.7"

__all__ = [
    # Exceptions
    "OutlookConnectionError",
    "FolderNotFoundError",
    "LLMError",
    "AppError",
    "DomainError",
    "InfrastructureError",
    "UserVisibleError",
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
