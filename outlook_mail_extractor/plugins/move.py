"""Move To Folder Plugin"""

from ..models import PluginExecutionResult
from . import BasePlugin, PluginConfig, register_plugin


@register_plugin
class MoveToFolderPlugin(BasePlugin):
    """Move email to folder based on LLM response"""

    name = "move_to_folder"
    default_system_prompt = """你是一個郵件分類助手。分析以下郵件內容，判斷應該移動到哪個資料夾。

可用的資料夾類別：
- 會議/Meeting：關於會議、行程的郵件
- 帳單/Bill：帳單、發票、付款相關
- 技術支援/TechSupport：技術問題、故障回報
- 採購/Purchase：採購相關郵件
- 其他/Other：無法分類的郵件

回覆時只輸出 JSON，不要有任何其他文字、解釋或 markdown 格式。"""

    default_response_json_format = {
        "move": '{"action": "move", "folder": "資料夾名稱"}',
        "no_move": '{"action": "move", "folder": ""}',
    }
    FOLDER_MAPPING = {
        "會議": "會議",
        "meeting": "會議",
        "帳單": "帳單",
        "bill": "帳單",
        "技術支援": "技術支援",
        "techsupport": "技術支援",
        "採購": "採購",
        "purchase": "採購",
        "其他": "其他",
        "other": "其他",
    }

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = self._load_config(config)

    def _load_config(self, config: dict) -> PluginConfig:
        return PluginConfig(
            enabled=config.get("enabled", True),
            system_prompt=config.get("system_prompt", self.default_system_prompt),
            response_format=config.get("response_format", "json"),
            override_prompt=config.get("override_prompt"),
            response_json_format=config.get(
                "response_json_format", self.default_response_json_format
            ),
        )

    async def execute(
        self,
        email_data: dict,
        llm_response: str,
        outlook_client,
    ) -> PluginExecutionResult:
        """Move email to folder based on LLM response"""
        try:
            response_data = self._parse_response(llm_response)
            if not response_data.get("action") == "move":
                return self.skipped_result(
                    message="Action is not move",
                    code="action_mismatch",
                )

            folder_name = response_data.get("folder", "")
            if not folder_name:
                return self.skipped_result(
                    message="Folder is empty",
                    code="empty_folder",
                )

            # Map folder name to canonical name
            canonical_folder = self._map_folder(folder_name)

            # Get the message from email data
            message = email_data.get("_message")
            if not message:
                return self.failed_result(
                    message="Missing _message in email_data",
                    code="missing_message",
                )

            # Get destination folder
            account = email_data.get("_account")
            try:
                dest_folder = outlook_client.get_folder(
                    account, canonical_folder, create_if_missing=True
                )
                message.Move(dest_folder)
                return self.success_result(message="Message moved")
            except Exception as e:
                return self.retriable_failed_result(
                    message=f"Move failed: {e}",
                    code="move_failed",
                )

        except Exception as e:
            return self.retriable_failed_result(
                message=f"Unexpected error: {e}",
                code="unexpected_error",
            )

    def _map_folder(self, folder_name: str) -> str:
        """Map folder name to canonical folder"""
        return self.FOLDER_MAPPING.get(folder_name.lower(), folder_name)
