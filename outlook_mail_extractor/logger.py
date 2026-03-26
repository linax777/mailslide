"""Logging utilities and runtime-configurable session manager."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

from .i18n import t

DEFAULT_DISPLAY_LEVEL = "INFO"


class LogSessionManager:
    """Manage loguru sink lifecycle for one runtime context."""

    def __init__(
        self,
        log_dir: Path = Path("logs"),
        log_config_path: Path = Path("config/logging.yaml"),
    ):
        self._log_dir = Path(log_dir)
        self._log_config_path = Path(log_config_path)
        self._ui_sink_callback: Callable[[str], None] | None = None
        self._current_log_path: Path | None = None
        self._display_level: str = DEFAULT_DISPLAY_LEVEL

    def _load_display_level(self) -> str:
        """Load display level from logging yaml config."""
        try:
            if self._log_config_path.exists():
                with open(self._log_config_path, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                return config.get("logging", {}).get(
                    "display_level",
                    DEFAULT_DISPLAY_LEVEL,
                )
        except Exception:
            pass
        return DEFAULT_DISPLAY_LEVEL

    def _ui_sink(self, message: str) -> None:
        """Write log messages to registered UI callback."""
        if self._ui_sink_callback:
            self._ui_sink_callback(message.strip())

    def set_ui_sink(self, callback: Callable[[str], None] | None) -> None:
        """Set UI sink callback."""
        self._ui_sink_callback = callback

    def start_session(self, enable_ui_sink: bool = False) -> Path:
        """Start a new log session and reconfigure sinks."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._display_level = self._load_display_level()

        logger.remove()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self._log_dir / f"session_{timestamp}.log"
        self._current_log_path = log_path

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

        if enable_ui_sink and self._ui_sink_callback:
            logger.add(
                self._ui_sink,
                level="INFO",
                format="{time:HH:mm:ss} | {level} | {message}",
            )

        logger.info(t("log.logger.session_started", level=self._display_level))
        return log_path

    def get_current_log_path(self) -> Path | None:
        """Get current log path for active session."""
        return self._current_log_path

    def get_display_level(self) -> str:
        """Get display level for current session manager."""
        return self._display_level

    def set_display_level(self, level: str) -> None:
        """Set display level for current session manager."""
        self._display_level = level.upper()


_DEFAULT_LOGGER_MANAGER = LogSessionManager()


class LoggerManager:
    """Backward-compatible static namespace for default manager."""

    set_ui_sink = staticmethod(_DEFAULT_LOGGER_MANAGER.set_ui_sink)
    start_session = staticmethod(_DEFAULT_LOGGER_MANAGER.start_session)
    get_current_log_path = staticmethod(_DEFAULT_LOGGER_MANAGER.get_current_log_path)
    get_display_level = staticmethod(_DEFAULT_LOGGER_MANAGER.get_display_level)
    set_display_level = staticmethod(_DEFAULT_LOGGER_MANAGER.set_display_level)


def get_default_logger_manager() -> LogSessionManager:
    """Return process-wide default logger manager."""
    return _DEFAULT_LOGGER_MANAGER


def get_logger():
    """Get shared loguru logger instance."""
    return logger
