"""Add Category Plugin"""

from ..models import PluginExecutionResult
from . import BasePlugin, PluginCapability, PluginConfig, register_plugin


@register_plugin
class AddCategoryPlugin(BasePlugin):
    """Add categories/labels to email based on LLM response"""

    name = "add_category"
    capabilities = {PluginCapability.REQUIRES_LLM}
    default_system_prompt = """你是一個郵件分類助手。分析以下郵件內容，選擇適當的分類標籤。

可用的分類：
- Meeting (會議)
- Bill (帳單)
- Important (重要)
- Urgent (緊急)
- Personal (個人)
- Work (工作)
- Newsletter (電子報)

回覆時只輸出 JSON，不要有任何其他文字、解釋或 markdown 格式。"""

    default_response_json_format = {
        "has_category": '{"action": "category", "categories": ["分類1", "分類2"]}',
        "no_category": '{"action": "category", "categories": []}',
    }
    VALID_CATEGORIES = {
        "meeting",
        "會議",
        "bill",
        "帳單",
        "important",
        "重要",
        "urgent",
        "緊急",
        "personal",
        "個人",
        "work",
        "工作",
        "newsletter",
        "電子報",
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
        """Add categories to email based on LLM response"""
        del outlook_client
        try:
            response_data = self._parse_response(llm_response)
            if not response_data.get("action") == "category":
                return self.skipped_result(
                    message="Action is not category",
                    code="action_mismatch",
                )

            categories = response_data.get("categories", [])
            if not categories:
                return self.skipped_result(
                    message="No categories provided",
                    code="empty_categories",
                )

            # Filter valid categories
            valid_categories = [
                c for c in categories if c.lower() in self.VALID_CATEGORIES
            ]
            if not valid_categories:
                return self.skipped_result(
                    message="No valid categories",
                    code="invalid_categories",
                    details={"categories": categories},
                )

            # Get the message from email data
            message = email_data.get("_message")
            if not message:
                return self.failed_result(
                    message="Missing _message in email_data",
                    code="missing_message",
                )

            # Set categories (Outlook uses comma-separated string)
            existing = getattr(message, "Categories", "") or ""
            new_categories = ", ".join(valid_categories)
            if existing:
                message.Categories = f"{existing}, {new_categories}"
            else:
                message.Categories = new_categories
            message.Save()
            return self.success_result(
                message="Categories added",
                details={"categories": valid_categories},
            )

        except Exception as e:
            return self.retriable_failed_result(
                message=f"Unexpected error: {e}",
                code="unexpected_error",
            )
