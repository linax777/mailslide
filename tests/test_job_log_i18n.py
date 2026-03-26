from pathlib import Path

from outlook_mail_extractor.i18n import set_language
from outlook_mail_extractor.services.job_execution import JobExecutionService
import outlook_mail_extractor.services.job_execution as job_execution_module


class _DummyLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: str) -> None:
        self.messages.append(message)


class _FakeLoggerManager:
    def __init__(self, current: Path | None = None) -> None:
        self._current = current

    def set_ui_sink(self, callback):
        del callback

    def start_session(self, enable_ui_sink: bool = False) -> Path:
        del enable_ui_sink
        self._current = Path("logs/new.log")
        return self._current

    def get_current_log_path(self) -> Path | None:
        return self._current

    def get_display_level(self) -> str:
        return "INFO"

    def set_display_level(self, level: str) -> None:
        del level


def test_ensure_log_session_uses_zh_tw_message() -> None:
    set_language("zh-TW")
    fake_logger = _DummyLogger()
    service = JobExecutionService(
        logger_manager=_FakeLoggerManager(Path("logs/existing.log"))
    )

    original = job_execution_module.get_logger
    job_execution_module.get_logger = lambda: fake_logger
    try:
        service._ensure_log_session()
    finally:
        job_execution_module.get_logger = original

    assert fake_logger.messages
    assert "使用現有日誌 session" in fake_logger.messages[0]


def test_ensure_log_session_uses_en_us_message() -> None:
    set_language("en-US")
    fake_logger = _DummyLogger()
    service = JobExecutionService(
        logger_manager=_FakeLoggerManager(Path("logs/existing.log"))
    )

    original = job_execution_module.get_logger
    job_execution_module.get_logger = lambda: fake_logger
    try:
        service._ensure_log_session()
    finally:
        job_execution_module.get_logger = original

    assert fake_logger.messages
    assert "Reusing existing log session" in fake_logger.messages[0]
