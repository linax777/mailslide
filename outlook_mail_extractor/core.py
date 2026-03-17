"""Outlook connection and email processing core module"""

from pathlib import Path

import pythoncom
import win32com.client

from .llm import LLMClient, load_llm_config
from .logger import LoggerManager, get_logger
from .models import (
    CheckStatus,
    EmailAnalysisResult,
    LLMConfigStatus,
    PluginResult,
)
from .parser import clean_invisible_chars, extract_main_content, parse_tables
from .plugins import get_plugin, load_plugin_configs


class OutlookConnectionError(Exception):
    """Cannot connect to Outlook"""

    pass


class FolderNotFoundError(Exception):
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


class EmailProcessor:
    """Email processing logic"""

    def __init__(
        self,
        client: OutlookClient,
        preserve_reply_thread: bool = True,
        max_length: int = 800,
    ):
        """Initialize email processor."""
        self._client = client
        self._preserve_reply_thread = preserve_reply_thread
        self._max_length = max_length

    def extract_email_data(self, message, max_length: int | None = None) -> dict:
        """Extract data from single email"""
        raw_body = str(message.Body) if getattr(message, "Body", None) else ""
        html_body = str(message.HTMLBody) if getattr(message, "HTMLBody", None) else ""
        clean_body = extract_main_content(
            raw_body,
            html_body,
            max_length=max_length or self._max_length,
            subject=str(message.Subject) if getattr(message, "Subject", None) else "",
            preserve_reply_thread=self._preserve_reply_thread,
        )

        return {
            "subject": message.Subject,
            "sender": (
                message.SenderEmailAddress
                if hasattr(message, "SenderEmailAddress")
                else message.SenderName
            ),
            "received": str(message.ReceivedTime),
            "body": clean_body,
            "tables": parse_tables(html_body),
            "_message": message,  # Keep reference for actions
            "_account": None,  # Will be set by caller
        }

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
        account_name = job_config.get("account")
        source_folder = job_config.get("source", "Inbox")
        destination_folder = job_config.get("destination")
        limit = job_config.get("limit", 10)
        body_max_length = job_config.get("body_max_length", self._max_length)

        # Get source folder
        src_folder = self._client.get_folder(account_name, source_folder)

        # Get destination folder if specified
        dst_folder = None
        if destination_folder:
            dst_folder = self._client.get_folder(
                account_name,
                destination_folder,
                create_if_missing=True,
            )

        # Get messages from source folder (sorted by date, newest first)
        messages = src_folder.Items
        messages.Sort("[ReceivedTime]", True)

        # Get messages up to limit
        msg_list = []
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
        if plugin_configs:
            for plugin_name in plugin_names:
                plugin = get_plugin(plugin_name, plugin_configs.get(plugin_name))
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
                dst_folder,
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
        dst_folder=None,
        body_max_length: int | None = None,
    ) -> EmailAnalysisResult:
        """Process single email with LLM and plugins"""
        logger = get_logger()

        # Extract email data
        email_data = self.extract_email_data(message, max_length=body_max_length)
        email_data["_account"] = account_name

        subject = email_data.get("subject", "Unknown")
        logger.info(f"處理郵件: {subject}")

        # If no LLM or plugins, just return basic data
        if not llm_client or not plugins:
            return EmailAnalysisResult(
                email_subject=subject,
                llm_response="",
                plugin_results=[],
                success=True,
            )

        # Build user prompt with email content
        user_prompt = self._build_email_prompt(email_data)

        # Collect system prompts from all plugins
        system_prompts = []
        plugins_needing_llm = []
        plugins_no_llm = []
        for plugin in plugins:
            if not plugin.config.enabled:
                continue
            prompt = plugin.build_effective_prompt()
            if prompt:
                system_prompts.append(prompt)
                plugins_needing_llm.append(plugin)
            else:
                plugins_no_llm.append(plugin)

        # Execute plugins that don't need LLM first
        plugin_results = []
        error_msg = ""
        if not dry_run:
            for plugin in plugins_no_llm:
                logger.info(f"執行 Plugin (無需 LLM): {plugin.name}")
                try:
                    plugin_success = await plugin.execute(email_data, "", self._client)
                    plugin_results.append(
                        PluginResult(
                            plugin_name=plugin.name,
                            success=plugin_success,
                            message="Success" if plugin_success else "Failed",
                        )
                    )
                except Exception as e:
                    logger.exception(f"Plugin {plugin.name} error: {e}")
                    plugin_results.append(
                        PluginResult(
                            plugin_name=plugin.name,
                            success=False,
                            message=f"Error: {e}",
                        )
                    )

        # If no plugins need LLM, return early
        if not system_prompts:
            if dst_folder and not dry_run and not no_move:
                try:
                    message.Move(dst_folder)
                except Exception as e:
                    error_msg = f"Move failed: {e}"
                    logger.error(error_msg)
            return EmailAnalysisResult(
                email_subject=subject,
                llm_response="",
                plugin_results=plugin_results,
                success=True,
                error_message=error_msg,
            )

        # Combine system prompts
        combined_system = "\n\n---\n\n".join(system_prompts)

        logger = get_logger()

        # Call LLM
        llm_response = ""
        success = True

        try:
            llm_response = llm_client.chat(combined_system, user_prompt)
            logger.debug(f"LLM 回覆: {llm_response}")
        except Exception as e:
            success = False
            error_msg = str(e)
            logger.error(f"LLM 呼叫失敗: {e}")

        # Execute plugins that need LLM
        if success and not dry_run:
            for plugin in plugins_needing_llm:
                if plugin.config.enabled:
                    # Check if plugin should be skipped based on LLM response
                    if plugin.name == "create_appointment":
                        try:
                            import json
                            import re

                            clean = re.sub(r"^```json\s*", "", llm_response.strip())
                            clean = re.sub(r"\s*```$", "", clean)
                            json_match = re.search(r"\{[^}]+\}", clean, re.DOTALL)
                            if json_match:
                                resp_data = json.loads(json_match.group())
                                if resp_data.get(
                                    "action"
                                ) == "appointment" and not resp_data.get(
                                    "create", False
                                ):
                                    logger.info(
                                        f"跳過 Plugin {plugin.name}: create 為 false"
                                    )
                                    continue
                        except Exception:
                            pass

                    logger.info(f"執行 Plugin: {plugin.name}")
                    try:
                        plugin_success = await plugin.execute(
                            email_data, llm_response, self._client
                        )
                        plugin_results.append(
                            PluginResult(
                                plugin_name=plugin.name,
                                success=plugin_success,
                                message="Success" if plugin_success else "Failed",
                            )
                        )
                        if plugin_success:
                            logger.info(f"Plugin {plugin.name}: Success")
                        else:
                            logger.warning(
                                f"Plugin {plugin.name}: Failed (回覆非預期格式)"
                            )
                    except Exception as e:
                        logger.exception(f"Plugin {plugin.name} error: {e}")
                        plugin_results.append(
                            PluginResult(
                                plugin_name=plugin.name,
                                success=False,
                                message=f"Error: {e}",
                            )
                        )

        # Move email to destination folder if specified
        if dst_folder and success and not dry_run and not no_move:
            try:
                message.Move(dst_folder)
            except Exception as e:
                error_msg = f"Move failed: {e}"

        return EmailAnalysisResult(
            email_subject=subject,
            llm_response=llm_response,
            plugin_results=plugin_results,
            success=success,
            error_message=error_msg,
        )

    def _build_email_prompt(self, email_data: dict) -> str:
        """Build user prompt from email data"""
        parts = []
        parts.append(f"Subject: {email_data.get('subject', '')}")
        parts.append(f"From: {email_data.get('sender', '')}")
        parts.append(f"Received: {email_data.get('received', '')}")
        parts.append(f"\nBody:\n{email_data.get('body', '')}")

        tables = email_data.get("tables", [])
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
            message=f"Ready - {config.provider}: {config.model}",
            provider=config.provider,
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
    preserve_reply_thread: bool = True,
    max_length: int = 800,
) -> dict:
    """
    Process config file with LLM analysis and plugins.

    Args:
        config_file: Config file path
        dry_run: Test mode
        no_move: Skip moving emails to destination folder
        preserve_reply_thread: Keep RE/FW thread content when parsing bodies
        max_length: Fallback body max length when config does not override

    Returns:
        All job results
    """
    logger = get_logger()
    client: OutlookClient | None = None
    llm_client: LLMClient | None = None

    existing_log_path = LoggerManager.get_current_log_path()
    if existing_log_path:
        logger.info(f"使用現有日誌 session: {existing_log_path}")
    else:
        log_path = LoggerManager.start_session(enable_ui_sink=False)
        logger.info(f"開始執行，日誌文件: {log_path}")
    logger.info(
        f"Config: {config_file}, Dry-run: {dry_run}, No-move: {no_move}, "
        f"Preserve-reply-thread: {preserve_reply_thread}"
    )

    try:
        from .config import load_config

        config = load_config(config_file)
        configured_max_length = config.get("body_max_length", max_length)
        client = OutlookClient()
        client.connect()

        # Try to load LLM config
        llm_config = load_llm_config()
        if llm_config.api_base:
            llm_client = LLMClient(llm_config)
            logger.info(f"LLM 客戶端已初始化: {llm_config.model}")

        # Load plugin configs
        plugin_configs = load_plugin_configs()
        logger.info(f"已載入 {len(plugin_configs)} 個插件配置")

        processor = EmailProcessor(
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
    except Exception as e:
        logger.exception(f"執行失敗: {e}")
        raise
    finally:
        if llm_client:
            llm_client.close()
        if client and client.is_connected:
            client.disconnect()
            logger.info("已斷開 Outlook 連接")
