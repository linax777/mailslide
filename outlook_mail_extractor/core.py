"""Outlook connection and email processing core module"""

from pathlib import Path
from collections.abc import Callable
from typing import Any

import pythoncom
import win32com.client

from .adapters import OutlookMailActionAdapter
from .llm import LLMClient, load_llm_config
from .logger import get_logger
from .models import (
    CheckStatus,
    DomainError,
    EmailDTO,
    EmailAnalysisResult,
    InfrastructureError,
    LLMConfigStatus,
    PluginExecutionResult,
    PluginExecutionStatus,
    PluginResult,
    UserVisibleError,
)
from .parser import extract_main_content, parse_tables
from .plugins import PluginCapability, get_plugin, load_plugin_configs
from .runtime import RuntimeContext, get_runtime_context


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
        clean_body = extract_main_content(
            raw_body,
            html_body,
            max_length=max_length or self._max_length,
            subject=str(message.Subject) if getattr(message, "Subject", None) else "",
            preserve_reply_thread=self._preserve_reply_thread,
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
            tables=parse_tables(html_body),
        )

    def _normalize_plugin_execution_result(
        self,
        plugin_name: str,
        execute_result: bool | PluginExecutionResult,
    ) -> PluginExecutionResult:
        """Normalize legacy bool plugin returns into structured results."""
        if isinstance(execute_result, PluginExecutionResult):
            return execute_result

        if execute_result:
            return PluginExecutionResult(
                status=PluginExecutionStatus.SUCCESS,
                message="Success",
            )

        return PluginExecutionResult(
            status=PluginExecutionStatus.FAILED,
            code="legacy_false",
            message=f"Plugin {plugin_name} returned False",
        )

    def _build_plugin_result(
        self,
        plugin_name: str,
        execute_result: bool | PluginExecutionResult,
    ) -> PluginResult:
        """Build PluginResult from legacy/new plugin result types."""
        normalized = self._normalize_plugin_execution_result(
            plugin_name, execute_result
        )
        return PluginResult(
            plugin_name=plugin_name,
            success=normalized.success,
            status=normalized.status,
            code=normalized.code,
            message=normalized.message,
            details=normalized.details,
        )

    async def process_job(
        self,
        job_config: dict,
        llm_client: LLMClient | None = None,
        plugin_configs: dict | None = None,
        dry_run: bool = False,
        no_move: bool = False,
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
        limit = job_config.get("limit", 10)
        body_max_length = job_config.get("body_max_length", self._max_length)

        # Get source folder
        src_folder = self._client.get_folder(account_name, source_folder)

        # Get destination folder if specified
        destination_folder_name = (
            str(destination_folder) if destination_folder else None
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

        logger = get_logger()
        if not msg_list:
            logger.info(f"Job {job_config.get('name', 'Unnamed Job')} 沒有可處理的郵件")

        # Initialize plugins (optional, for backward compatibility)
        plugin_names = job_config.get("plugins", [])
        plugins = []
        plugin_configs = plugin_configs or {}
        job_prompt_profiles = job_config.get("plugin_prompt_profiles", {})
        for plugin_name in plugin_names:
            raw_config = plugin_configs.get(plugin_name, {})
            resolved_config = _resolve_plugin_prompt(
                plugin_name, raw_config, job_prompt_profiles, logger
            )
            plugin = get_plugin(plugin_name, resolved_config)
            if plugin:
                plugins.append(plugin)

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
                body_max_length,
            )
            results.append(result)

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
        body_max_length: int | None = None,
    ) -> EmailAnalysisResult:
        """Process single email with LLM and plugins"""
        logger = get_logger()

        # Extract email data
        email_data = self.extract_email_data(message, max_length=body_max_length)
        action_port = OutlookMailActionAdapter(
            client=self._client,
            message=message,
            account_name=account_name,
        )

        subject = email_data.subject or "Unknown"
        logger.info(f"處理郵件: {subject}")

        # Collect system prompts from all plugins
        system_prompts = []
        plugins_needing_llm = []
        plugins_no_llm = []
        for plugin in plugins:
            if not plugin.config.enabled:
                continue
            prompt = plugin.build_effective_prompt()
            if plugin.requires_llm():
                if prompt:
                    system_prompts.append(prompt)
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
                try:
                    plugin_execute_result = await plugin.execute(
                        email_data, "", action_port
                    )
                    plugin_result = self._build_plugin_result(
                        plugin.name,
                        plugin_execute_result,
                    )
                    plugin_results.append(plugin_result)
                    if (
                        plugin.supports(PluginCapability.MOVES_MESSAGE)
                        and plugin_result.success
                    ):
                        moved_by_plugin = True

                    if plugin_result.status == PluginExecutionStatus.SUCCESS:
                        logger.info(f"Plugin {plugin.name}: success")
                    elif plugin_result.status == PluginExecutionStatus.SKIPPED:
                        logger.info(
                            f"Plugin {plugin.name}: skipped ({plugin_result.message})"
                        )
                    else:
                        logger.warning(
                            f"Plugin {plugin.name}: {plugin_result.status.value} "
                            f"({plugin_result.message})"
                        )
                except (DomainError, InfrastructureError, UserVisibleError) as e:
                    logger.exception(f"Plugin {plugin.name} error: {e}")
                    plugin_results.append(
                        PluginResult(
                            plugin_name=plugin.name,
                            success=False,
                            status=PluginExecutionStatus.FAILED,
                            code="typed_error",
                            message=f"Error: {e}",
                        )
                    )
                except Exception as e:
                    wrapped = InfrastructureError(
                        f"Unhandled plugin error ({plugin.name}): {e}"
                    )
                    logger.exception(str(wrapped))
                    plugin_results.append(
                        PluginResult(
                            plugin_name=plugin.name,
                            success=False,
                            status=PluginExecutionStatus.RETRIABLE_FAILED,
                            code="unhandled_error",
                            message=f"Error: {wrapped}",
                        )
                    )

        # Call LLM when there are plugins that require it.
        llm_response = ""
        success = True

        if plugins_needing_llm:
            if not llm_client:
                success = False
                error_msg = "LLM client not available"
                logger.warning("略過需 LLM 的插件：LLM client not available")
                for plugin in plugins_needing_llm:
                    plugin_results.append(
                        PluginResult(
                            plugin_name=plugin.name,
                            success=False,
                            status=PluginExecutionStatus.FAILED,
                            code="llm_unavailable",
                            message="LLM client not available",
                        )
                    )
            else:
                user_prompt = self._build_email_prompt(email_data)
                combined_system = "\n\n---\n\n".join(system_prompts)

                try:
                    llm_response = llm_client.chat(combined_system, user_prompt)
                    logger.debug(f"LLM 回覆: {llm_response}")
                except Exception as e:
                    success = False
                    error_msg = str(e)
                    logger.error(f"LLM 呼叫失敗: {e}")

                if success and not dry_run:
                    for plugin in plugins_needing_llm:
                        skip_result = plugin.should_skip_by_response(llm_response)
                        if skip_result:
                            plugin_result = self._build_plugin_result(
                                plugin.name,
                                skip_result,
                            )
                            plugin_results.append(plugin_result)
                            logger.info(
                                f"跳過 Plugin {plugin.name}: {plugin_result.message}"
                            )
                            continue

                        logger.info(f"執行 Plugin: {plugin.name}")
                        try:
                            plugin_execute_result = await plugin.execute(
                                email_data, llm_response, action_port
                            )
                            plugin_result = self._build_plugin_result(
                                plugin.name,
                                plugin_execute_result,
                            )
                            plugin_results.append(plugin_result)
                            if (
                                plugin.supports(PluginCapability.MOVES_MESSAGE)
                                and plugin_result.success
                            ):
                                moved_by_plugin = True

                            if plugin_result.status == PluginExecutionStatus.SUCCESS:
                                logger.info(f"Plugin {plugin.name}: success")
                            elif plugin_result.status == PluginExecutionStatus.SKIPPED:
                                logger.info(
                                    f"Plugin {plugin.name}: skipped ({plugin_result.message})"
                                )
                            else:
                                logger.warning(
                                    f"Plugin {plugin.name}: {plugin_result.status.value} "
                                    f"({plugin_result.message})"
                                )
                        except (
                            DomainError,
                            InfrastructureError,
                            UserVisibleError,
                        ) as e:
                            logger.exception(f"Plugin {plugin.name} error: {e}")
                            plugin_results.append(
                                PluginResult(
                                    plugin_name=plugin.name,
                                    success=False,
                                    status=PluginExecutionStatus.FAILED,
                                    code="typed_error",
                                    message=f"Error: {e}",
                                )
                            )
                        except Exception as e:
                            wrapped = InfrastructureError(
                                f"Unhandled plugin error ({plugin.name}): {e}"
                            )
                            logger.exception(str(wrapped))
                            plugin_results.append(
                                PluginResult(
                                    plugin_name=plugin.name,
                                    success=False,
                                    status=PluginExecutionStatus.RETRIABLE_FAILED,
                                    code="unhandled_error",
                                    message=f"Error: {wrapped}",
                                )
                            )

        # Move email to destination folder if specified
        if (
            destination_folder_name
            and success
            and not dry_run
            and not no_move
            and not moved_by_plugin
        ):
            try:
                action_port.move_to_folder(destination_folder_name)
            except Exception as e:
                error_msg = f"Move failed: {e}"
                logger.error(error_msg)

        return EmailAnalysisResult(
            email_subject=subject,
            llm_response=llm_response,
            plugin_results=plugin_results,
            success=success,
            error_message=error_msg,
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
