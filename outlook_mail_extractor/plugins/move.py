"""Move To Folder Plugin"""

import json
import re

from . import BasePlugin, register_plugin


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

回覆 JSON 格式：
{"action": "move", "folder": "資料夾名稱"}"""

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

    async def execute(
        self,
        email_data: dict,
        llm_response: str,
        outlook_client,
    ) -> bool:
        """Move email to folder based on LLM response"""
        try:
            response_data = self._parse_response(llm_response)
            if not response_data.get("action") == "move":
                return False

            folder_name = response_data.get("folder", "")
            if not folder_name:
                return False

            # Map folder name to canonical name
            canonical_folder = self._map_folder(folder_name)

            # Get the message from email data
            message = email_data.get("_message")
            if not message:
                return False

            # Get destination folder
            account = email_data.get("_account")
            try:
                dest_folder = outlook_client.get_folder(
                    account, canonical_folder, create_if_missing=True
                )
                message.Move(dest_folder)
                return True
            except Exception:
                return False

        except Exception:
            return False

    def _parse_response(self, response: str) -> dict:
        """Parse JSON from LLM response"""
        import json
        import re

        # Remove markdown code block wrappers
        clean = re.sub(r"^```json\s*", "", response.strip())
        clean = re.sub(r"\s*```$", "", clean)
        clean = clean.strip()

        # Try to extract JSON from response
        json_match = re.search(r"\{[^}]+\}", clean, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def _map_folder(self, folder_name: str) -> str:
        """Map folder name to canonical folder"""
        return self.FOLDER_MAPPING.get(folder_name.lower(), folder_name)
