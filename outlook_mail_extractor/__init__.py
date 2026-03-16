"""Outlook Mail Extractor - 讀取 Outlook Classic 郵件的 Python 模組"""

from .config import load_config, validate_config
from .core import (
    EmailProcessor,
    FolderNotFoundError,
    OutlookClient,
    OutlookConnectionError,
    process_config_file,
)
from .parser import clean_content, clean_invisible_chars, parse_tables

__version__ = "1.0.0"

__all__ = [
    # 例外類別
    "OutlookConnectionError",
    "FolderNotFoundError",
    # 核心類別
    "OutlookClient",
    "EmailProcessor",
    # 便利函式
    "process_config_file",
    # 設定檔
    "load_config",
    "validate_config",
    # 工具函式
    "clean_content",
    "clean_invisible_chars",
    "parse_tables",
]
