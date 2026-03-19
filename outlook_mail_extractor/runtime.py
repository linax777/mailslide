"""Runtime context and dependency wiring helpers."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .logger import LogSessionManager


class LoggerManagerProtocol(Protocol):
    """Minimal logger manager interface required by runtime."""

    def set_ui_sink(self, callback: Callable[[str], None] | None) -> None: ...

    def start_session(self, enable_ui_sink: bool = False) -> Path: ...

    def get_current_log_path(self) -> Path | None: ...

    def get_display_level(self) -> str: ...

    def set_display_level(self, level: str) -> None: ...


@dataclass(frozen=True)
class RuntimePaths:
    """Filesystem paths used by CLI/TUI runtime."""

    project_root: Path
    config_dir: Path
    config_file: Path
    llm_config_file: Path
    plugins_dir: Path
    logging_config_file: Path
    logs_dir: Path
    readme_file: Path


@dataclass
class RuntimeContext:
    """Injectable runtime dependencies for app/services."""

    paths: RuntimePaths
    logger_manager: LoggerManagerProtocol
    client_factory: Callable[[], Any]


def _default_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_runtime_paths(project_root: Path | None = None) -> RuntimePaths:
    """Create runtime paths from project root."""
    root = project_root or _default_project_root()
    config_dir = root / "config"
    return RuntimePaths(
        project_root=root,
        config_dir=config_dir,
        config_file=config_dir / "config.yaml",
        llm_config_file=config_dir / "llm-config.yaml",
        plugins_dir=config_dir / "plugins",
        logging_config_file=config_dir / "logging.yaml",
        logs_dir=root / "logs",
        readme_file=root / "README.md",
    )


def _default_client_factory() -> Any:
    from .core import OutlookClient

    return OutlookClient()


def create_runtime_context(project_root: Path | None = None) -> RuntimeContext:
    """Build a default runtime context for current environment."""
    paths = build_runtime_paths(project_root=project_root)
    logger_manager = LogSessionManager(
        log_dir=paths.logs_dir,
        log_config_path=paths.logging_config_file,
    )
    return RuntimeContext(
        paths=paths,
        logger_manager=logger_manager,
        client_factory=_default_client_factory,
    )


_DEFAULT_RUNTIME_CONTEXT = create_runtime_context()


def get_runtime_context() -> RuntimeContext:
    """Get process-wide default runtime context."""
    return _DEFAULT_RUNTIME_CONTEXT
