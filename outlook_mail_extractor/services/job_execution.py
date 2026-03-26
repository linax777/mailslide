"""Application service that orchestrates config-driven job execution."""

import json
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from ..config import load_config
from ..core import EmailProcessor, OutlookClient
from ..i18n import t
from ..llm import LLMClient, load_llm_config
from ..logger import get_default_logger_manager, get_logger
from ..models import DomainError, InfrastructureError, UserVisibleError
from ..parser import clean_invisible_chars
from ..plugins import load_plugin_configs, load_plugin_modules
from ..runtime import LoggerManagerProtocol


class JobExecutionService:
    """Orchestrate end-to-end execution for all enabled jobs."""

    def __init__(
        self,
        client_factory: Callable[[], OutlookClient] = OutlookClient,
        processor_factory: Callable[..., EmailProcessor] = EmailProcessor,
        config_loader: Callable[[Path | str], dict] = load_config,
        llm_config_loader: Callable[[str | None], Any] = load_llm_config,
        llm_client_factory: Callable[[Any], LLMClient] = LLMClient,
        plugin_config_loader: Callable[[Path], dict] = load_plugin_configs,
        logger_manager: LoggerManagerProtocol | None = None,
        default_llm_config_path: Path = Path("config/llm-config.yaml"),
        default_plugin_config_dir: Path = Path("config/plugins"),
    ):
        self._client_factory = client_factory
        self._processor_factory = processor_factory
        self._config_loader = config_loader
        self._llm_config_loader = llm_config_loader
        self._llm_client_factory = llm_client_factory
        self._plugin_config_loader = plugin_config_loader
        self._logger_manager = logger_manager or get_default_logger_manager()
        self._default_llm_config_path = default_llm_config_path
        self._default_plugin_config_dir = default_plugin_config_dir

    def _resolve_runtime_paths(
        self, config_file: Path | str
    ) -> tuple[Path, Path, Path]:
        """Resolve LLM/plugin config paths relative to target config file."""
        config_path = Path(config_file)
        config_dir = config_path.parent

        llm_config_path = config_dir / "llm-config.yaml"
        resolved_llm_config = (
            llm_config_path
            if llm_config_path.exists()
            else self._default_llm_config_path
        )

        plugin_config_dir = config_dir / "plugins"
        resolved_plugin_dir = (
            plugin_config_dir
            if plugin_config_dir.exists()
            else self._default_plugin_config_dir
        )
        return config_path, resolved_llm_config, Path(resolved_plugin_dir)

    def _ensure_log_session(self) -> None:
        """Start a log session only when none exists."""
        logger = get_logger()
        existing_log_path = self._logger_manager.get_current_log_path()
        if existing_log_path:
            logger.info(t("log.job_execution.reuse_session", path=existing_log_path))
            return

        log_path = self._logger_manager.start_session(enable_ui_sink=False)
        logger.info(t("log.job_execution.started", path=log_path))

    async def process_config_file(
        self,
        config_file: Path | str = "config/config.yaml",
        dry_run: bool = False,
        no_move: bool = False,
        preserve_reply_thread: bool = False,
        max_length: int = 800,
    ) -> dict:
        """
        Process all enabled jobs from a config file.

        Args:
            config_file: Config file path
            dry_run: Test mode
            no_move: Skip moving emails to destination folder
            preserve_reply_thread: Keep RE/FW thread content when parsing bodies
            max_length: Fallback body max length when config does not override

        Returns:
            Job execution results indexed by job name
        """
        logger = get_logger()
        client: OutlookClient | None = None
        llm_client: LLMClient | None = None

        self._ensure_log_session()
        logger.info(
            t(
                "log.job_execution.config",
                path=config_file,
                dry_run=dry_run,
                no_move=no_move,
                preserve_reply_thread=preserve_reply_thread,
            )
        )

        _config_path, resolved_llm_config, resolved_plugin_dir = (
            self._resolve_runtime_paths(config_file)
        )
        logger.info(t("log.job_execution.llm_config_path", path=resolved_llm_config))
        logger.info(t("log.job_execution.plugin_config_dir", path=resolved_plugin_dir))

        try:
            config = self._config_loader(config_file)
            configured_max_length = config.get("body_max_length", max_length)
            default_llm_mode = config.get("llm_mode", "per_plugin")
            configured_plugin_modules = config.get("plugin_modules", [])
            if isinstance(configured_plugin_modules, list):
                loaded_modules = load_plugin_modules(configured_plugin_modules)
                if loaded_modules:
                    logger.info(
                        t(
                            "log.job_execution.plugin_modules_loaded",
                            modules=", ".join(loaded_modules),
                        )
                    )

            client = self._client_factory()
            client.connect()

            llm_config = self._llm_config_loader(str(resolved_llm_config))
            if llm_config.api_base:
                llm_client = self._llm_client_factory(llm_config)
                logger.info(
                    t(
                        "log.job_execution.llm_client_initialized",
                        model=llm_config.model,
                    )
                )

            plugin_configs = self._plugin_config_loader(resolved_plugin_dir)
            logger.info(
                t("log.job_execution.plugin_config_loaded", count=len(plugin_configs))
            )

            processor = self._processor_factory(
                client,
                preserve_reply_thread=preserve_reply_thread,
                max_length=configured_max_length,
            )
            all_results = {}

            for job in config.get("jobs", []):
                if job.get("enable", True) is False:
                    job_name = job.get("name", "Unnamed Job")
                    logger.info(t("log.job_execution.job_skipped", name=job_name))
                    continue

                job_name = job.get("name", "Unnamed Job")
                logger.info(t("log.job_execution.job_started", name=job_name))
                job_started_at = perf_counter()
                results = await processor.process_job(
                    job,
                    llm_client=llm_client,
                    plugin_configs=plugin_configs,
                    dry_run=dry_run,
                    no_move=no_move,
                    llm_mode=default_llm_mode,
                )
                all_results[job_name] = results
                logger.info(
                    t(
                        "log.job_execution.job_finished",
                        name=job_name,
                        count=len(results),
                    )
                )
                logger.info(
                    f"METRIC job_execution {json.dumps({'job_name': job_name, 'job_elapsed_ms': round((perf_counter() - job_started_at) * 1000, 2), 'mail_count': len(results)}, ensure_ascii=False)}"
                )

            logger.info(t("log.job_execution.completed"))
            return clean_invisible_chars(all_results)
        except (DomainError, InfrastructureError, UserVisibleError) as e:
            logger.exception(t("log.job_execution.failed", error=e))
            raise
        except Exception as e:
            logger.exception(t("log.job_execution.failed", error=e))
            raise InfrastructureError(f"Unhandled processing failure: {e}") from e
        finally:
            if llm_client:
                llm_client.close()
            if client and client.is_connected:
                client.disconnect()
                logger.info(t("log.job_execution.outlook_disconnected"))
