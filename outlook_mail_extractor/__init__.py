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
from .logger import LoggerManager, get_logger
from .models import (
    AppError,
    CheckStatus,
    ConfigStatus,
    DomainError,
    EmailAnalysisResult,
    InfrastructureError,
    LLMConfigStatus,
    OutlookStatus,
    PluginResult,
    SystemStatus,
    UserVisibleError,
)
from .parser import clean_content, clean_invisible_chars, parse_tables

__version__ = "1.0.0"

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
    "EmailAnalysisResult",
    # Utilities
    "process_config_file",
    "clean_content",
    "clean_invisible_chars",
    "parse_tables",
    # Logger
    "LoggerManager",
    "get_logger",
]
