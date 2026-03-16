"""Create Appointment Plugin"""

import json
import re
from datetime import datetime

from loguru import logger

from . import BasePlugin, register_plugin


@register_plugin
class CreateAppointmentPlugin(BasePlugin):
    """Create calendar appointment from email based on LLM response"""

    name = "create_appointment"
    default_system_prompt = """你是一個日曆助手。分析以下郵件內容，判斷是否包含預約、會議或行程資訊。

回覆時只輸出 JSON，不要有任何其他文字、解釋或 markdown 格式。

需要建立約會時：
{"action": "appointment", "create": true, "subject": "約會主題", "start": "2024-01-15T14:00:00", "end": "2024-01-15T15:00:00", "location": "會議室或線上連結", "body": "額外備註"}

不需要建立約會時：
{"action": "appointment", "create": false}"""

    async def execute(
        self,
        email_data: dict,
        llm_response: str,
        outlook_client,
    ) -> bool:
        """Create calendar appointment from email based on LLM response"""
        try:
            response_data = self._parse_response(llm_response)
            logger.info(f"[create_appointment] Parsed: {response_data}")

            if response_data.get("action") != "appointment":
                logger.info(f"[create_appointment] Action is not appointment")
                return False

            if not response_data.get("create", False):
                logger.info(f"[create_appointment] create is false")
                return False

            subject = response_data.get("subject", "")
            if not subject:
                logger.info(f"[create_appointment] subject is empty")
                return False

            start_str = response_data.get("start", "")
            end_str = response_data.get("end", "")

            try:
                start = self._parse_datetime(start_str) if start_str else None
                end = self._parse_datetime(end_str) if end_str else None
            except Exception as e:
                logger.info(f"[create_appointment] Datetime parse error: {e}")
                return False

            if not start or not end:
                logger.info(
                    f"[create_appointment] start or end is None: start={start}, end={end}"
                )
                return False

            account = email_data.get("_account")
            if not account:
                logger.info(f"[create_appointment] account is missing in email_data")
                return False
            logger.info(f"[create_appointment] Using account: {account}")

            try:
                calendar = outlook_client.get_calendar_folder(account)
                logger.info(f"[create_appointment] Got calendar folder: {calendar}")
            except Exception as e:
                logger.info(
                    f"[create_appointment] Failed to get calendar folder: {type(e).__name__}: {e}"
                )
                return False

            # Create appointment item
            appointment = calendar.Items.Add(1)  # 1 = olAppointmentItem
            appointment.Subject = subject
            appointment.Start = start
            appointment.End = end
            appointment.Location = response_data.get("location", "")
            appointment.Body = response_data.get("body", "")
            appointment.Save()
            return True

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

        # Try to find JSON object
        json_match = re.search(r"\{[^}]+\}", clean, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def _parse_datetime(self, dt_str: str) -> datetime | None:
        """Parse ISO format datetime string"""
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",  # Date only format
        ]
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None
