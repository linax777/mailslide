from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

LOG_DIR = Path("logs")
LOG_CONFIG_PATH = Path("config/logging.yaml")

DEFAULT_DISPLAY_LEVEL = "INFO"


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


class LoggerManager:
    _current_log_path: Path | None = None
    _display_level: str = DEFAULT_DISPLAY_LEVEL

    @classmethod
    def start_session(cls) -> Path:
        """開始新的 session，創建新的日誌文件"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # 載入 display level 設定
        cls._display_level = _load_display_level()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = LOG_DIR / f"session_{timestamp}.log"
        cls._current_log_path = log_path

        logger.remove()
        logger.add(
            log_path,
            rotation="100 MB",
            retention="1 week",
            compression="zip",
            level="DEBUG",
            format="[{time:YYYY-MM-DD HH:mm:ss}][{level}] {message}",
            encoding="utf-8",
            enqueue=True,
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
