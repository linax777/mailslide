"""Add Category Plugin"""

from . import BasePlugin, register_plugin


@register_plugin
class AddCategoryPlugin(BasePlugin):
    """Add categories/labels to email based on LLM response"""

    name = "add_category"
    default_system_prompt = """你是一個郵件分類助手。分析以下郵件內容，選擇適當的分類標籤。

可用的分類：
- Meeting (會議)
- Bill (帳單)
- Important (重要)
- Urgent (緊急)
- Personal (個人)
- Work (工作)
- Newsletter (電子報)

回覆 JSON 格式：
{"action": "category", "categories": ["分類1", "分類2"]}"""

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

    async def execute(
        self,
        email_data: dict,
        llm_response: str,
        outlook_client,
    ) -> bool:
        """Add categories to email based on LLM response"""
        try:
            response_data = self._parse_response(llm_response)
            if not response_data.get("action") == "category":
                return False

            categories = response_data.get("categories", [])
            if not categories:
                return False

            # Filter valid categories
            valid_categories = [
                c for c in categories if c.lower() in self.VALID_CATEGORIES
            ]
            if not valid_categories:
                return False

            # Get the message from email data
            message = email_data.get("_message")
            if not message:
                return False

            # Set categories (Outlook uses comma-separated string)
            existing = getattr(message, "Categories", "") or ""
            new_categories = ", ".join(valid_categories)
            if existing:
                message.Categories = f"{existing}, {new_categories}"
            else:
                message.Categories = new_categories
            message.Save()
            return True

        except Exception:
            return False
