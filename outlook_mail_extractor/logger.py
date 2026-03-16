from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import yaml
from loguru import logger

LOG_DIR = Path("logs")
LOG_CONFIG_PATH = Path("config/logging.yaml")

DEFAULT_DISPLAY_LEVEL = "INFO"

_ui_sink_callback: Optional[Callable] = None


def _load_display_level() -> str:
    """從 config/logging.yaml 載入 display_level"""
    try:
        if LOG_CONFIG_PATH.exists():
            with open(LOG_CONFIG_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                return config.get("logging", {}).get(
                    "display_level", DEFAULT_DISPLAY_LEVEL
                )
    except Exception:
        pass
    return DEFAULT_DISPLAY_LEVEL


def _ui_sink(message: str) -> None:
    """UI sink - 將日誌寫入 Textual Log widget"""
    if _ui_sink_callback:
        _ui_sink_callback(message.strip())


class LoggerManager:
    _current_log_path: Path | None = None
    _display_level: str = DEFAULT_DISPLAY_LEVEL

    @classmethod
    def set_ui_sink(cls, callback: Optional[Callable]) -> None:
        """設置 UI sink 的回調函數"""
        global _ui_sink_callback
        _ui_sink_callback = callback

    @classmethod
    def start_session(cls, enable_ui_sink: bool = False) -> Path:
        """開始新的 session，創建新的日誌文件"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # 載入 display level 設定
        cls._display_level = _load_display_level()

        # 清除所有現有的 sinks
        logger.remove()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = LOG_DIR / f"session_{timestamp}.log"
        cls._current_log_path = log_path

        # File sink
        logger.add(
            log_path,
            rotation="100 MB",
            retention="1 week",
            level="DEBUG",
            format="[{time:YYYY-MM-DD HH:mm:ss}][{level}] {message}",
            encoding="utf-8",
            enqueue=False,
            diagnose=False,
        )

        # UI sink (if enabled)
        if enable_ui_sink and _ui_sink_callback:
            logger.add(
                _ui_sink,
                level="INFO",
                format="{time:HH:mm:ss} | {level} | {message}",
            )

        logger.info(f"日誌 session 開始，display_level: {cls._display_level}")

        return log_path

    @classmethod
    def get_current_log_path(cls) -> Path | None:
        return cls._current_log_path

    @classmethod
    def get_display_level(cls) -> str:
        return cls._display_level

    @classmethod
    def set_display_level(cls, level: str) -> None:
        cls._display_level = level.upper()


def get_logger():
    """取得 logger 實例"""
    return logger
