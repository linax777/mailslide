"""Application service that orchestrates config-driven job execution."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from time import perf_counter
from typing import Any, NoReturn

from ..config import load_config
from ..core import (
    EmailProcessor,
    OutlookClient,
    _resolve_plugin_prompt,
)
from ..i18n import t
from ..llm import LLMClient, load_llm_config
from ..logger import get_default_logger_manager, get_logger
from ..models import DomainError, InfrastructureError, UserVisibleError
from ..parser import clean_invisible_chars
from ..plugins import get_plugin, load_plugin_configs
from ..plugins.loader import load_external_plugin_modules
from ..plugins.download_attachments_paths import (
    DEFAULT_FULL_PATH_BUDGET,
    DEFAULT_JOB_FOLDER_MAX_LENGTH,
    DEFAULT_MIN_STARTUP_STEM_LENGTH,
    build_job_folder_key,
    has_viable_startup_filename_budget,
)
from ..runtime import LoggerManagerProtocol
from .dependency_guard import DependencyGuardService


class JobExecutionService:
    """Orchestrate end-to-end execution for all enabled jobs."""

    _STARTUP_CODE_OUTPUT_DIR_INVALID = "startup_output_dir_invalid"
    _STARTUP_CODE_PATH_BUDGET_INVALID = "startup_path_budget_invalid"

    @staticmethod
    def _is_absolute_output_path(raw_path: str) -> bool:
        """Treat platform-native and Windows absolute paths as absolute."""
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return True

        windows_candidate = PureWindowsPath(raw_path)
        return windows_candidate.is_absolute()

    @staticmethod
    def _resolve_windows_root_path(raw_path: str) -> Path | None:
        """Resolve Windows root path for drive/UNC absolute paths."""
        windows_candidate = PureWindowsPath(raw_path)
        if not windows_candidate.is_absolute():
            return None

        if windows_candidate.drive:
            return Path(f"{windows_candidate.drive}\\")

        anchor = windows_candidate.anchor
        if anchor:
            return Path(anchor)

        return None

    @staticmethod
    def _coerce_positive_int(value: object, *, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value if value > 0 else default
        if isinstance(value, str):
            try:
                parsed = int(value.strip())
            except ValueError:
                return default
            return parsed if parsed > 0 else default
        return default

    def __init__(
        self,
        client_factory: Callable[[], OutlookClient] = OutlookClient,
        processor_factory: Callable[..., EmailProcessor] = EmailProcessor,
        config_loader: Callable[[Path | str], dict] = load_config,
        llm_config_loader: Callable[[str | None], Any] = load_llm_config,
        llm_client_factory: Callable[[Any], LLMClient] = LLMClient,
        plugin_config_loader: Callable[[Path], dict] = load_plugin_configs,
        dependency_guard_service: DependencyGuardService | None = None,
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
        self._dependency_guard_service = (
            dependency_guard_service or DependencyGuardService()
        )
        self._logger_manager = logger_manager or get_default_logger_manager()
        self._default_llm_config_path = default_llm_config_path
        self._default_plugin_config_dir = default_plugin_config_dir

    def _job_requires_llm(
        self,
        job: dict[str, Any],
        plugin_configs: dict[str, dict[str, Any]],
    ) -> bool:
        """Return True when any enabled plugin in the job requires LLM."""
        plugin_names = job.get("plugins", [])
        if not isinstance(plugin_names, list):
            return False

        job_prompt_profiles = job.get("plugin_prompt_profiles", {})
        if not isinstance(job_prompt_profiles, dict):
            job_prompt_profiles = {}
        logger = get_logger()

        for plugin_name in plugin_names:
            if not isinstance(plugin_name, str):
                continue

            plugin_config = plugin_configs.get(plugin_name, {})
            safe_plugin_config = (
                plugin_config if isinstance(plugin_config, dict) else {}
            )
            resolved_plugin_config = _resolve_plugin_prompt(
                plugin_name,
                safe_plugin_config,
                job_prompt_profiles,
                logger,
            )
            plugin = get_plugin(plugin_name, resolved_plugin_config)
            if plugin is None or not plugin.config.enabled:
                continue

            if plugin.requires_llm():
                return True

        return False

    def _enabled_jobs_require_llm(
        self,
        jobs: list[dict[str, Any]],
        plugin_configs: dict[str, dict[str, Any]],
    ) -> bool:
        """Return True when any enabled job contains LLM-required plugins."""
        for job in jobs:
            if not isinstance(job, dict) or job.get("enable", True) is False:
                continue
            if self._job_requires_llm(job, plugin_configs):
                return True
        return False

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

    def _normalize_plugin_output_paths(
        self,
        plugin_configs: dict[str, dict[str, Any]],
        base_dir: Path,
    ) -> dict[str, dict[str, Any]]:
        """Resolve relative plugin output paths against config directory."""
        normalized: dict[str, dict[str, Any]] = {}
        for plugin_name, plugin_config in plugin_configs.items():
            if not isinstance(plugin_config, dict):
                normalized[plugin_name] = {}
                continue

            next_config = dict(plugin_config)
            for key in ("output_file", "output_dir"):
                raw_path = next_config.get(key)
                if not isinstance(raw_path, str) or not raw_path.strip():
                    continue

                candidate = Path(raw_path).expanduser()
                if self._is_absolute_output_path(raw_path):
                    continue

                next_config[key] = str((base_dir / candidate).resolve())

            normalized[plugin_name] = next_config
        return normalized

    def _validate_download_attachment_startup_paths(
        self,
        jobs: list[dict[str, Any]],
        plugin_configs: dict[str, dict[str, Any]],
    ) -> None:
        """Validate download_attachments startup path requirements for enabled jobs."""

        def raise_startup_error(code: str, message: str) -> NoReturn:
            raise DomainError(f"{code}: {message}")

        download_plugin_config = plugin_configs.get("download_attachments", {})
        if not isinstance(download_plugin_config, dict):
            return

        if download_plugin_config.get("enabled", True) is False:
            return

        uses_download_plugin = False
        for job in jobs:
            if not isinstance(job, dict) or job.get("enable", True) is False:
                continue

            raw_plugins = job.get("plugins", [])
            if not isinstance(raw_plugins, list):
                continue
            if "download_attachments" in raw_plugins:
                uses_download_plugin = True
                break

        if not uses_download_plugin:
            return

        raw_output_dir = download_plugin_config.get("output_dir")
        if not isinstance(raw_output_dir, str):
            raise_startup_error(
                self._STARTUP_CODE_OUTPUT_DIR_INVALID,
                "download_attachments requires non-empty output_dir in plugin config",
            )
        output_dir_text = raw_output_dir.strip()
        if not output_dir_text:
            raise_startup_error(
                self._STARTUP_CODE_OUTPUT_DIR_INVALID,
                "download_attachments requires non-empty output_dir in plugin config",
            )

        output_dir = Path(output_dir_text).expanduser()
        if output_dir.exists() and not output_dir.is_dir():
            raise_startup_error(
                self._STARTUP_CODE_OUTPUT_DIR_INVALID,
                "download_attachments output_dir must be a directory path",
            )

        probe_path = output_dir if output_dir.exists() else output_dir.parent
        if not str(probe_path).strip():
            raise_startup_error(
                self._STARTUP_CODE_OUTPUT_DIR_INVALID,
                "download_attachments output_dir parent path is not resolvable",
            )

        if probe_path.exists() and not probe_path.is_dir():
            raise_startup_error(
                self._STARTUP_CODE_OUTPUT_DIR_INVALID,
                "download_attachments output_dir parent is not a directory",
            )

        windows_root = self._resolve_windows_root_path(output_dir_text)
        if windows_root is not None and not windows_root.exists():
            raise_startup_error(
                self._STARTUP_CODE_OUTPUT_DIR_INVALID,
                "download_attachments output_dir parent root is not available",
            )

        anchor = probe_path.anchor.strip()
        if anchor:
            anchor_path = Path(anchor)
            if not anchor_path.exists():
                raise_startup_error(
                    self._STARTUP_CODE_OUTPUT_DIR_INVALID,
                    "download_attachments output_dir parent root is not available",
                )

        full_path_budget = self._coerce_positive_int(
            download_plugin_config.get("full_path_budget", DEFAULT_FULL_PATH_BUDGET),
            default=DEFAULT_FULL_PATH_BUDGET,
        )
        job_folder_max_length = self._coerce_positive_int(
            download_plugin_config.get(
                "job_folder_max_length", DEFAULT_JOB_FOLDER_MAX_LENGTH
            ),
            default=DEFAULT_JOB_FOLDER_MAX_LENGTH,
        )

        for job in jobs:
            if not isinstance(job, dict) or job.get("enable", True) is False:
                continue
            raw_plugins = job.get("plugins", [])
            if (
                not isinstance(raw_plugins, list)
                or "download_attachments" not in raw_plugins
            ):
                continue

            job_name = str(job.get("name", "job")).strip() or "job"
            folder_key = build_job_folder_key(
                job_name,
                max_length=job_folder_max_length,
            )
            candidate_parent = output_dir / folder_key
            extension_viable = has_viable_startup_filename_budget(
                parent_dir=candidate_parent,
                full_path_budget=full_path_budget,
                min_stem_length=DEFAULT_MIN_STARTUP_STEM_LENGTH,
                extension=".txt",
            )
            extensionless_viable = has_viable_startup_filename_budget(
                parent_dir=candidate_parent,
                full_path_budget=full_path_budget,
                min_stem_length=DEFAULT_MIN_STARTUP_STEM_LENGTH,
                extension="",
            )
            if not extension_viable or not extensionless_viable:
                raise_startup_error(
                    self._STARTUP_CODE_PATH_BUDGET_INVALID,
                    (
                        "download_attachments output path budget is not viable for "
                        f"job '{job_name}'"
                    ),
                )

    async def process_config_file(
        self,
        config_file: Path | str = "config/config.yaml",
        dry_run: bool = False,
        no_move: bool = False,
        preserve_reply_thread: bool = False,
        max_length: int = 800,
        cancel_requested: Callable[[], bool] | None = None,
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

        config_path, resolved_llm_config, resolved_plugin_dir = (
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
                module_names = [
                    str(module_path).strip()
                    for module_path in configured_plugin_modules
                    if str(module_path).strip()
                ]
                loaded_modules = load_external_plugin_modules(module_names)
                if loaded_modules:
                    logger.info(
                        t(
                            "log.job_execution.plugin_modules_loaded",
                            modules=", ".join(loaded_modules),
                        )
                    )

            plugin_configs = self._plugin_config_loader(resolved_plugin_dir)
            plugin_configs = self._normalize_plugin_output_paths(
                plugin_configs,
                base_dir=config_path.parent,
            )
            logger.info(
                t("log.job_execution.plugin_config_loaded", count=len(plugin_configs))
            )

            jobs = config.get("jobs", [])
            typed_jobs = jobs if isinstance(jobs, list) else []
            self._validate_download_attachment_startup_paths(
                typed_jobs,
                plugin_configs,
            )
            if self._enabled_jobs_require_llm(typed_jobs, plugin_configs):
                self._dependency_guard_service.ensure_llm_runtime_compatible()

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

            processor = self._processor_factory(
                client,
                preserve_reply_thread=preserve_reply_thread,
                max_length=configured_max_length,
            )
            all_results = {}

            for job in typed_jobs:
                if cancel_requested and cancel_requested():
                    logger.info("Cancellation requested. Stopping job execution.")
                    raise asyncio.CancelledError("Job execution cancelled by user")

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
                    cancel_requested=cancel_requested,
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
        except asyncio.CancelledError:
            logger.info("Job execution cancelled by user.")
            raise
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
