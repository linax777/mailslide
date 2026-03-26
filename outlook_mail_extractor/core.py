"""Outlook connection and email processing core module"""

import json
from pathlib import Path
from time import perf_counter
from collections.abc import Callable
from typing import Any

import pythoncom
import win32com.client

from .adapters import OutlookMailActionAdapter
from .llm import LLMClient, load_llm_config
from .llm_dispatcher import (
    LLM_MODE_PER_PLUGIN,
    LLM_MODE_SHARE_DEPRECATED as _LLM_MODE_SHARE_DEPRECATED,
    dispatch_llm_plugins,
    resolve_llm_mode,
)
from .logger import get_logger
from .models import (
    CheckStatus,
    DomainError,
    EmailDTO,
    EmailAnalysisResult,
    InfrastructureError,
    LLMConfigStatus,
)
from .move_policy import select_move_target
from .parser import clean_content, parse_email_html
from .plugins import get_plugin, load_plugin_configs
from .plugin_runner import execute_plugin
from .runtime import RuntimeContext, get_runtime_context


LLM_MODE_SHARE_DEPRECATED = _LLM_MODE_SHARE_DEPRECATED


class OutlookConnectionError(InfrastructureError):
    """Cannot connect to Outlook"""

    pass


class FolderNotFoundError(DomainError):
    """Folder not found"""

    pass


class OutlookClient:
    """Outlook COM connection management"""

    def __init__(self):
        self._outlook = None
        self._mapi = None
        self._connected = False

    def connect(self) -> None:
        """
        Establish Outlook connection.

        Raises:
            OutlookConnectionError: When connection fails
        """
        try:
            pythoncom.CoInitialize()
            self._outlook = win32com.client.Dispatch("Outlook.Application")
            self._mapi = self._outlook.GetNamespace("MAPI")
            self._connected = True
        except Exception as e:
            pythoncom.CoUninitialize()
            raise OutlookConnectionError(
                f"Cannot connect to Outlook. Please ensure Microsoft Outlook Classic "
                f"is installed and logged in.\nDetails: {e}"
            ) from e

    def disconnect(self) -> None:
        """Close Outlook connection"""
        if self._connected:
            pythoncom.CoUninitialize()
            self._outlook = None
            self._mapi = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self._connected

    def list_accounts(self) -> list[str]:
        """List all available accounts"""
        if not self._connected:
            raise OutlookConnectionError("Not connected, call connect() first")
        return [store.Name for store in self._mapi.Folders]

    def _normalize_account_name(self, value: str) -> str:
        """Normalize account/store names for exact matching."""
        return value.strip().casefold()

    def _resolve_account_root(self, account: str):
        """Resolve an Outlook account/store root with strict matching."""
        requested = self._normalize_account_name(account)
        for store in self._mapi.Folders:
            store_name = getattr(store, "Name", "")
            if self._normalize_account_name(store_name) == requested:
                return store
        raise FolderNotFoundError(f"Account not found: {account}")

    def get_folder(
        self, account: str, folder_path: str, create_if_missing: bool = False
    ):
        """Get folder from specified account"""
        if not self._connected:
            raise OutlookConnectionError("Not connected, call connect() first")

        acc_root = self._resolve_account_root(account)

        current_folder = acc_root
        parts = folder_path.replace("\\", "/").split("/")
        for part in parts:
            if not part:
                continue
            try:
                current_folder = current_folder.Folders[part]
            except Exception:
                if create_if_missing:
                    current_folder.Folders.Add(part)
                    current_folder = current_folder.Folders[part]
                else:
                    raise FolderNotFoundError(f"Path not found: {part}")
        return current_folder

    def get_calendar_folder(self, account: str):
        """Get default calendar folder for specified account (uses localized name)"""
        if not self._connected:
            raise OutlookConnectionError("Not connected, call connect() first")

        OL_FOLDER_CALENDAR = 9
        try:
            store = self._resolve_account_root(account).Store
            return store.GetDefaultFolder(OL_FOLDER_CALENDAR)
        except Exception as e:
            raise FolderNotFoundError(f"GetDefaultFolder failed: {e}") from e


def _resolve_plugin_prompt(
    plugin_name: str,
    raw_config: dict,
    job_prompt_profiles: dict,
    logger,
) -> dict:
    """
    Resolve effective system prompt for a plugin based on job profile assignment.

    Resolution order (first wins):
    1. job.plugin_prompt_profiles[plugin] -> plugin.prompt_profiles[profile].system_prompt
    2. plugin.default_prompt_profile -> plugin.prompt_profiles[profile].system_prompt
    3. plugin.system_prompt (existing behavior, fallback)

    Args:
        plugin_name: Name of the plugin
        raw_config: Raw plugin config from yaml
        job_prompt_profiles: job.plugin_prompt_profiles dict (plugin_name -> profile_key)
        logger: Logger instance for warning messages

    Returns:
        Resolved config dict with override_prompt injected if needed
    """
    resolved = dict(raw_config)

    profiles = raw_config.get("prompt_profiles", {})
    if not profiles:
        return resolved

    job_profile = job_prompt_profiles.get(plugin_name)
    if job_profile:
        if job_profile in profiles:
            profile_entry = profiles[job_profile]
            profile_prompt = (
                profile_entry.get("system_prompt")
                if isinstance(profile_entry, dict)
                else profile_entry
            )
            if profile_prompt:
                resolved["override_prompt"] = profile_prompt
                return resolved
        else:
            logger.warning(
                f"Job 指定了不存在的 prompt profile '{job_profile}' for plugin '{plugin_name}'，"
                f"將 fallback 到預設行為"
            )

    default_profile = raw_config.get("default_prompt_profile")
    if default_profile and default_profile in profiles:
        profile_entry = profiles[default_profile]
        profile_prompt = (
            profile_entry.get("system_prompt")
            if isinstance(profile_entry, dict)
            else profile_entry
        )
        if profile_prompt:
            resolved["override_prompt"] = profile_prompt

    return resolved


class EmailProcessor:
    """Email processing logic"""

    def __init__(
        self,
        client: OutlookClient,
        preserve_reply_thread: bool = False,
        max_length: int = 800,
    ):
        """Initialize email processor."""
        self._client = client
        self._preserve_reply_thread = preserve_reply_thread
        self._max_length = max_length

    def extract_email_data(self, message, max_length: int | None = None) -> EmailDTO:
        """Extract data from single email"""
        logger = get_logger()
        raw_body = str(message.Body) if getattr(message, "Body", None) else ""
        html_body = str(message.HTMLBody) if getattr(message, "HTMLBody", None) else ""
        subject = str(message.Subject) if getattr(message, "Subject", None) else ""
        parsed_html = parse_email_html(html_body, use_cache=True)
        html_clean_body = clean_content(
            parsed_html.text,
            max_length=max_length or self._max_length,
            subject=subject,
            preserve_reply_thread=self._preserve_reply_thread,
        )
        plain_clean_body = clean_content(
            raw_body,
            max_length=max_length or self._max_length,
            subject=subject,
            preserve_reply_thread=self._preserve_reply_thread,
        )
        clean_body = (
            html_clean_body
            if len(html_clean_body) >= len(plain_clean_body)
            else plain_clean_body
        )
        logger.debug(
            "郵件內文清理完成: plain=%d chars, html=%d chars, cleaned=%d chars",
            len(raw_body),
            len(html_body),
            len(clean_body),
        )

        return EmailDTO(
            subject=str(getattr(message, "Subject", "")),
            sender=str(
                message.SenderEmailAddress
                if hasattr(message, "SenderEmailAddress")
                else getattr(message, "SenderName", "")
            ),
            received=str(getattr(message, "ReceivedTime", "")),
            body=clean_body,
            tables=parsed_html.tables,
            entry_id=str(getattr(message, "EntryID", "")),
        )

    async def process_job(
        self,
        job_config: dict,
        llm_client: LLMClient | None = None,
        plugin_configs: dict | None = None,
        dry_run: bool = False,
        no_move: bool = False,
        llm_mode: str = LLM_MODE_PER_PLUGIN,
    ) -> list[EmailAnalysisResult]:
        """
        Process single job with LLM analysis and plugins.

        Args:
            job_config: Job config dict with name, account, source, destination, limit
            llm_client: Optional LLM client for analysis
            plugin_configs: Plugin configurations
            dry_run: Test mode (don't execute actions)

        Returns:
            List of EmailAnalysisResult
        """
        account_name_raw = job_config.get("account")
        if not isinstance(account_name_raw, str) or not account_name_raw.strip():
            raise DomainError("Job account is required")
        account_name = account_name_raw
        source_folder = job_config.get("source", "Inbox")
        destination_folder = job_config.get("destination")
        manual_review_destination = job_config.get("manual_review_destination")
        limit = job_config.get("limit", 10)
        body_max_length = job_config.get("body_max_length", self._max_length)
        logger = get_logger()
        raw_job_llm_mode = job_config.get("llm_mode")
        effective_llm_mode = resolve_llm_mode(
            raw_job_llm_mode if raw_job_llm_mode is not None else llm_mode,
            logger,
        )

        # Get source folder
        src_folder = self._client.get_folder(account_name, source_folder)

        # Get destination folder if specified
        destination_folder_name = (
            str(destination_folder) if destination_folder else None
        )
        manual_review_destination_folder_name = (
            str(manual_review_destination) if manual_review_destination else None
        )

        # Get messages from source folder (sorted by date, newest first)
        messages = src_folder.Items
        messages.Sort("[ReceivedTime]", True)

        # Get messages up to limit
        msg_list: list[Any] = []
        msg = messages.GetFirst()
        while msg and len(msg_list) < limit:
            if getattr(msg, "Class", None) == 43:  # Mail item
                msg_list.append(msg)
            msg = messages.GetNext()

        if not msg_list:
            logger.info(f"Job {job_config.get('name', 'Unnamed Job')} 沒有可處理的郵件")

        # Initialize plugins (optional, for backward compatibility)
        plugin_names = job_config.get("plugins", [])
        plugins = []
        plugin_configs = plugin_configs or {}
        job_prompt_profiles = job_config.get("plugin_prompt_profiles", {})
        batch_flush_enabled = bool(job_config.get("batch_flush_enabled", True))
        for plugin_name in plugin_names:
            raw_config = plugin_configs.get(plugin_name, {})
            resolved_config = _resolve_plugin_prompt(
                plugin_name, raw_config, job_prompt_profiles, logger
            )
            plugin = get_plugin(plugin_name, resolved_config)
            if plugin:
                plugins.append(plugin)

        for plugin in plugins:
            begin_job = getattr(plugin, "begin_job", None)
            if callable(begin_job):
                begin_job({"batch_flush_enabled": batch_flush_enabled})

        # Process each email
        results = []
        for msg in msg_list:
            result = await self._process_email(
                msg,
                account_name,
                llm_client,
                plugins,
                dry_run,
                no_move,
                destination_folder_name,
                manual_review_destination_folder_name,
                body_max_length,
                effective_llm_mode,
            )
            results.append(result)

        for plugin in plugins:
            end_job = getattr(plugin, "end_job", None)
            if not callable(end_job):
                continue
            flush_result = end_job()
            if not flush_result:
                continue
            if flush_result.success:
                logger.info(
                    f"Plugin {plugin.name} finalize success: {flush_result.message}"
                )
                continue

            pending_rows = int(flush_result.details.get("pending_rows", 0))
            logger.warning(
                f"Plugin {plugin.name} finalize failed: {flush_result.message} "
                f"(pending_rows={pending_rows})"
            )

        total_mail_ms = sum(
            float(result.metrics.get("mail_elapsed_ms", 0.0))
            for result in results
            if isinstance(result.metrics, dict)
        )
        llm_call_count = sum(
            int(result.metrics.get("llm_call_count", 0))
            for result in results
            if isinstance(result.metrics, dict)
        )
        llm_elapsed_ms = sum(
            float(result.metrics.get("llm_elapsed_ms", 0.0))
            for result in results
            if isinstance(result.metrics, dict)
        )
        job_plugin_status_distribution = {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "retriable_failed": 0,
        }
        for result in results:
            if not isinstance(result.metrics, dict):
                continue
            distribution = result.metrics.get("plugin_status_distribution", {})
            if not isinstance(distribution, dict):
                continue
            for key in job_plugin_status_distribution:
                job_plugin_status_distribution[key] += int(distribution.get(key, 0))

        job_metric = {
            "job_name": job_config.get("name", "Unnamed Job"),
            "mail_count": len(results),
            "mail_elapsed_ms": round(total_mail_ms, 2),
            "llm_call_count": llm_call_count,
            "llm_elapsed_ms": round(llm_elapsed_ms, 2),
            "plugin_status_distribution": job_plugin_status_distribution,
            "batch_flush_enabled": batch_flush_enabled,
        }
        logger.info(f"METRIC job_summary {json.dumps(job_metric, ensure_ascii=False)}")

        return results

    async def _process_email(
        self,
        message,
        account_name: str,
        llm_client: LLMClient | None,
        plugins: list,
        dry_run: bool,
        no_move: bool,
        destination_folder_name: str | None = None,
        manual_review_destination_folder_name: str | None = None,
        body_max_length: int | None = None,
        llm_mode: str = LLM_MODE_PER_PLUGIN,
    ) -> EmailAnalysisResult:
        """Process single email with LLM and plugins"""
        logger = get_logger()
        mail_started_at = perf_counter()

        # Extract email data
        email_data = self.extract_email_data(message, max_length=body_max_length)
        action_port = OutlookMailActionAdapter(
            client=self._client,
            message=message,
            account_name=account_name,
        )

        subject = email_data.subject or "Unknown"
        logger.info(f"處理郵件: {subject}")

        # Split plugins by LLM requirement
        plugins_needing_llm = []
        plugins_no_llm = []
        for plugin in plugins:
            if not plugin.config.enabled:
                continue
            if plugin.requires_llm():
                plugins_needing_llm.append(plugin)
            else:
                plugins_no_llm.append(plugin)

        # Execute plugins that don't need LLM first
        plugin_results = []
        error_msg = ""
        moved_by_plugin = False
        if not dry_run:
            for plugin in plugins_no_llm:
                logger.info(f"執行 Plugin (無需 LLM): {plugin.name}")
                plugin_result, moved = await execute_plugin(
                    plugin,
                    email_data,
                    "",
                    action_port,
                    logger,
                )
                plugin_results.append(plugin_result)
                moved_by_plugin = moved_by_plugin or moved

        # Call LLM for plugins that require it.
        llm_response = ""
        success = True
        llm_call_count = 0
        llm_elapsed_ms = 0.0

        if plugins_needing_llm:
            llm_dispatch_result = await dispatch_llm_plugins(
                plugins=plugins_needing_llm,
                llm_client=llm_client,
                user_prompt=self._build_email_prompt(email_data),
                llm_mode=llm_mode,
                dry_run=dry_run,
                email_data=email_data,
                action_port=action_port,
                logger=logger,
            )
            plugin_results.extend(llm_dispatch_result.plugin_results)
            llm_response = llm_dispatch_result.llm_response
            success = llm_dispatch_result.success
            error_msg = llm_dispatch_result.error_message
            moved_by_plugin = moved_by_plugin or llm_dispatch_result.moved_by_plugin
            llm_call_count = llm_dispatch_result.llm_call_count
            llm_elapsed_ms = llm_dispatch_result.llm_elapsed_ms

        llm_plugin_names = {plugin.name for plugin in plugins_needing_llm}
        move_target_folder = select_move_target(
            plugin_results=plugin_results,
            llm_plugin_names=llm_plugin_names,
            destination_folder_name=destination_folder_name,
            manual_review_destination_folder_name=manual_review_destination_folder_name,
            success=success,
        )

        # Move email to selected folder when orchestrator still owns move behavior.
        if move_target_folder and not dry_run and not no_move and not moved_by_plugin:
            try:
                action_port.move_to_folder(move_target_folder)
            except Exception as e:
                error_msg = f"Move failed: {e}"
                logger.error(error_msg)

        plugin_status_distribution = {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "retriable_failed": 0,
        }
        for plugin_result in plugin_results:
            key = plugin_result.status.value
            if key in plugin_status_distribution:
                plugin_status_distribution[key] += 1

        mail_elapsed_ms = (perf_counter() - mail_started_at) * 1000
        mail_metric = {
            "subject": subject,
            "mail_elapsed_ms": round(mail_elapsed_ms, 2),
            "llm_call_count": llm_call_count,
            "llm_elapsed_ms": round(llm_elapsed_ms, 2),
            "plugin_status_distribution": plugin_status_distribution,
            "success": success,
        }
        logger.info(
            f"METRIC mail_summary {json.dumps(mail_metric, ensure_ascii=False)}"
        )

        return EmailAnalysisResult(
            email_subject=subject,
            llm_response=llm_response,
            plugin_results=plugin_results,
            success=success,
            error_message=error_msg,
            metrics={
                "mail_elapsed_ms": round(mail_elapsed_ms, 2),
                "llm_call_count": llm_call_count,
                "llm_elapsed_ms": round(llm_elapsed_ms, 2),
                "plugin_status_distribution": plugin_status_distribution,
            },
        )

    def _build_email_prompt(self, email_data: EmailDTO) -> str:
        """Build user prompt from email data"""
        parts = []
        parts.append(f"Subject: {email_data.subject}")
        parts.append(f"From: {email_data.sender}")
        parts.append(f"Received: {email_data.received}")
        parts.append(f"\nBody:\n{email_data.body}")

        tables = email_data.tables
        if tables:
            parts.append("\nTables found in email:")
            for i, table in enumerate(tables):
                parts.append(f"\nTable {i + 1}:")
                for row in table[:5]:  # Limit to first 5 rows
                    parts.append(str(row))

        return "\n".join(parts)


def check_llm_config(config_file: str | None = None) -> LLMConfigStatus:
    """Check LLM configuration status"""
    try:
        config = load_llm_config(config_file)
        return LLMConfigStatus(
            status=CheckStatus.OK,
            message=f"Ready - {config.model}",
            model=config.model,
        )
    except Exception as e:
        return LLMConfigStatus(
            status=CheckStatus.ERROR,
            message=str(e),
        )


async def process_config_file(
    config_file: Path | str = "config/config.yaml",
    dry_run: bool = False,
    no_move: bool = False,
    preserve_reply_thread: bool = False,
    max_length: int = 800,
    runtime_context: RuntimeContext | None = None,
    client_factory: Callable[[], OutlookClient] | None = None,
    processor_factory: Callable[..., EmailProcessor] = EmailProcessor,
    config_loader: Callable[[Path | str], dict] | None = None,
    llm_config_loader: Callable[[str | None], Any] = load_llm_config,
    llm_client_factory: Callable[[Any], LLMClient] = LLMClient,
    plugin_config_loader: Callable[[Path], dict] = load_plugin_configs,
) -> dict:
    """
    Process config file with LLM analysis and plugins.

    Args:
        config_file: Config file path
        dry_run: Test mode
        no_move: Skip moving emails to destination folder
        preserve_reply_thread: Keep RE/FW thread content when parsing bodies
        max_length: Fallback body max length when config does not override
        runtime_context: Optional runtime dependency context
        client_factory: Optional Outlook client factory override
        processor_factory: Email processor factory
        config_loader: Optional config loader override
        llm_config_loader: LLM config loader
        llm_client_factory: LLM client factory
        plugin_config_loader: Plugin config loader

    Returns:
        All job results
    """
    from .config import load_config
    from .services.job_execution import JobExecutionService

    context = runtime_context or get_runtime_context()
    resolved_client_factory = client_factory or context.client_factory
    resolved_config_loader = config_loader or load_config
    service = JobExecutionService(
        client_factory=resolved_client_factory,
        processor_factory=processor_factory,
        config_loader=resolved_config_loader,
        llm_config_loader=llm_config_loader,
        llm_client_factory=llm_client_factory,
        plugin_config_loader=plugin_config_loader,
        logger_manager=context.logger_manager,
        default_llm_config_path=context.paths.llm_config_file,
        default_plugin_config_dir=context.paths.plugins_dir,
    )
    return await service.process_config_file(
        config_file=config_file,
        dry_run=dry_run,
        no_move=no_move,
        preserve_reply_thread=preserve_reply_thread,
        max_length=max_length,
    )
