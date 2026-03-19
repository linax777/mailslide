"""Create Appointment Plugin"""

from datetime import datetime

from loguru import logger

from ..models import EmailDTO, MailActionPort, PluginExecutionResult
from .base import BasePlugin, PluginCapability, PluginConfig, register_plugin


@register_plugin
class CreateAppointmentPlugin(BasePlugin):
    """Create calendar appointment from email based on LLM response"""

    name = "create_appointment"
    capabilities = {
        PluginCapability.REQUIRES_LLM,
        PluginCapability.CAN_SKIP_BY_RESPONSE,
    }
    default_system_prompt = """你是一個日曆助手。分析以下郵件內容，判斷是否包含預約、會議或行程資訊。

回覆時只輸出 JSON，不要有任何其他文字、解釋或 markdown 格式。"""

    default_response_json_format = {
        "create_true": '{"action": "appointment", "create": true, "subject": "約會主題", "start": "2024-01-15T14:00:00", "end": "2024-01-15T15:00:00", "location": "會議室或線上連結", "body": "額外備註"}',
        "create_false": '{"action": "appointment", "create": false}',
    }
    default_recipients: list[str] = []

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = self._load_config(config)
        self.recipients: list[str] = config.get("recipients", self.default_recipients)

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

    def should_skip_by_response(
        self,
        llm_response: str,
    ) -> PluginExecutionResult | None:
        """Skip appointment creation when LLM explicitly says create=false."""
        if not self.supports(PluginCapability.CAN_SKIP_BY_RESPONSE):
            return None

        response_data = self._parse_response(llm_response)
        if response_data.get("action") == "appointment" and not response_data.get(
            "create", False
        ):
            return self.skipped_result(
                message="Skip by LLM response: create=false",
                code="llm_skip_condition",
            )
        return None

    async def execute(
        self,
        email_data: EmailDTO,
        llm_response: str,
        action_port: MailActionPort,
    ) -> PluginExecutionResult:
        """Create calendar appointment from email based on LLM response"""
        try:
            response_data = self._parse_response(llm_response)
            logger.info(f"[create_appointment] Parsed: {response_data}")

            if response_data.get("action") != "appointment":
                logger.info("[create_appointment] Action is not appointment")
                return self.skipped_result(
                    message="Action is not appointment",
                    code="action_mismatch",
                )

            if not response_data.get("create", False):
                logger.info("[create_appointment] create is false")
                return self.skipped_result(
                    message="Create flag is false",
                    code="create_false",
                )

            subject = response_data.get("subject", "")
            if not subject:
                logger.info("[create_appointment] subject is empty")
                return self.failed_result(
                    message="Missing subject",
                    code="missing_subject",
                )

            start_str = response_data.get("start", "")
            end_str = response_data.get("end", "")

            try:
                start = self._parse_datetime(start_str) if start_str else None
                end = self._parse_datetime(end_str) if end_str else None
            except Exception as e:
                logger.info(f"[create_appointment] Datetime parse error: {e}")
                return self.failed_result(
                    message=f"Datetime parse error: {e}",
                    code="invalid_datetime",
                )

            if not start or not end:
                logger.info(
                    f"[create_appointment] start or end is None: start={start}, end={end}"
                )
                return self.failed_result(
                    message="Missing or invalid start/end datetime",
                    code="missing_datetime",
                )

            try:
                action_port.create_appointment(
                    subject=subject,
                    start=start,
                    end=end,
                    location=response_data.get("location", ""),
                    body=response_data.get("body", ""),
                    recipients=self.recipients,
                )
            except Exception as e:
                logger.info(f"[create_appointment] Failed to create appointment: {e}")
                return self.retriable_failed_result(
                    message=f"Appointment creation failed: {e}",
                    code="appointment_create_failed",
                )

            return self.success_result(message="Appointment created")

        except Exception as e:
            return self.retriable_failed_result(
                message=f"Unexpected error: {e}",
                code="unexpected_error",
            )

    def _parse_datetime(self, dt_str: str) -> datetime | None:
        """Parse ISO format datetime string"""
        normalized = dt_str.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is not None:
                return parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            pass

        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",  # Date only format
        ]
        for fmt in formats:
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return None
