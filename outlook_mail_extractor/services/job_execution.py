"""Application service that orchestrates config-driven job execution."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import load_config
from ..core import EmailProcessor, OutlookClient
from ..llm import LLMClient, load_llm_config
from ..logger import LoggerManager, get_logger
from ..models import DomainError, InfrastructureError, UserVisibleError
from ..parser import clean_invisible_chars
from ..plugins import load_plugin_configs


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
    ):
        self._client_factory = client_factory
        self._processor_factory = processor_factory
        self._config_loader = config_loader
        self._llm_config_loader = llm_config_loader
        self._llm_client_factory = llm_client_factory
        self._plugin_config_loader = plugin_config_loader

    def _resolve_runtime_paths(
        self, config_file: Path | str
    ) -> tuple[Path, Path | None, Path]:
        """Resolve LLM/plugin config paths relative to target config file."""
        config_path = Path(config_file)
        config_dir = config_path.parent

        llm_config_path = config_dir / "llm-config.yaml"
        resolved_llm_config = llm_config_path if llm_config_path.exists() else None

        plugin_config_dir = config_dir / "plugins"
        resolved_plugin_dir = (
            plugin_config_dir if plugin_config_dir.exists() else Path("config/plugins")
        )
        return config_path, resolved_llm_config, resolved_plugin_dir

    def _ensure_log_session(self) -> None:
        """Start a log session only when none exists."""
        logger = get_logger()
        existing_log_path = LoggerManager.get_current_log_path()
        if existing_log_path:
            logger.info(f"使用現有日誌 session: {existing_log_path}")
            return

        log_path = LoggerManager.start_session(enable_ui_sink=False)
        logger.info(f"開始執行，日誌文件: {log_path}")

    async def process_config_file(
        self,
        config_file: Path | str = "config/config.yaml",
        dry_run: bool = False,
        no_move: bool = False,
        preserve_reply_thread: bool = True,
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
            f"Config: {config_file}, Dry-run: {dry_run}, No-move: {no_move}, "
            f"Preserve-reply-thread: {preserve_reply_thread}"
        )

        _config_path, resolved_llm_config, resolved_plugin_dir = (
            self._resolve_runtime_paths(config_file)
        )
        logger.info(
            f"LLM config path: {resolved_llm_config or 'config/llm-config.yaml'}"
        )
        logger.info(f"Plugin config dir: {resolved_plugin_dir}")

        try:
            config = self._config_loader(config_file)
            configured_max_length = config.get("body_max_length", max_length)

            client = self._client_factory()
            client.connect()

            llm_config = self._llm_config_loader(
                str(resolved_llm_config) if resolved_llm_config else None
            )
            if llm_config.api_base:
                llm_client = self._llm_client_factory(llm_config)
                logger.info(f"LLM 客戶端已初始化: {llm_config.model}")

            plugin_configs = self._plugin_config_loader(resolved_plugin_dir)
            logger.info(f"已載入 {len(plugin_configs)} 個插件配置")

            processor = self._processor_factory(
                client,
                preserve_reply_thread=preserve_reply_thread,
                max_length=configured_max_length,
            )
            all_results = {}

            for job in config.get("jobs", []):
                if job.get("enable", True) is False:
                    job_name = job.get("name", "Unnamed Job")
                    logger.info(f"跳过 Job (已停用): {job_name}")
                    continue

                job_name = job.get("name", "Unnamed Job")
                logger.info(f"開始處理 Job: {job_name}")
                results = await processor.process_job(
                    job,
                    llm_client=llm_client,
                    plugin_configs=plugin_configs,
                    dry_run=dry_run,
                    no_move=no_move,
                )
                all_results[job_name] = results
                logger.info(f"Job {job_name} 完成，處理 {len(results)} 封郵件")

            logger.info("執行完成")
            return clean_invisible_chars(all_results)
        except (DomainError, InfrastructureError, UserVisibleError) as e:
            logger.exception(f"執行失敗: {e}")
            raise
        except Exception as e:
            logger.exception(f"執行失敗: {e}")
            raise InfrastructureError(f"Unhandled processing failure: {e}") from e
        finally:
            if llm_client:
                llm_client.close()
            if client and client.is_connected:
                client.disconnect()
                logger.info("已斷開 Outlook 連接")
