"""Event Table Plugin"""

from datetime import datetime
from pathlib import Path

from loguru import logger
from openpyxl import Workbook, load_workbook

from ..models import EmailDTO, MailActionPort, PluginExecutionResult
from .base import BasePlugin, PluginCapability, PluginConfig, register_plugin


@register_plugin
class EventTablePlugin(BasePlugin):
    """Write extracted appointment data to an Excel table."""

    name = "event_table"
    capabilities = {PluginCapability.REQUIRES_LLM}
    default_system_prompt = """你是一個日曆助手。分析以下郵件內容，判斷是否包含預約、會議或行程資訊。

回覆時只輸出 JSON，不要有任何其他文字、解釋或 markdown 格式。"""
    default_response_json_format = {
        "create_true": '{"action": "appointment", "create": true, "subject": "約會主題", "start": "2024-01-15T14:00:00", "end": "2024-01-15T15:00:00", "location": "會議室或線上連結", "body": "額外備註"}',
        "create_false": '{"action": "appointment", "create": false}',
    }
    default_output_file = "output/events.xlsx"
    default_fields = [
        "email_subject",
        "email_sender",
        "email_received",
        "email_entry_id",
        "outlook_link",
        "event_subject",
        "start",
        "end",
        "location",
        "body",
        "logged_at",
    ]

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = self._load_config(config)
        self.output_file = config.get("output_file", self.default_output_file)
        self.fields = list(self.default_fields)
        if "fields" in config:
            logger.warning(
                "[event_table] 'fields' config is ignored; Excel schema is fixed"
            )

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
        email_data: EmailDTO,
        llm_response: str,
        action_port: MailActionPort,
    ) -> PluginExecutionResult:
        """Write appointment data into Excel when LLM asks to create."""
        del action_port
        try:
            response_data = self._parse_response(llm_response)
            if response_data.get("action") != "appointment":
                return self.skipped_result(
                    message="Action is not appointment",
                    code="action_mismatch",
                )

            if not response_data.get("create", False):
                return self.skipped_result(
                    message="Create flag is false",
                    code="create_false",
                )

            event_subject = response_data.get("subject", "")
            start_str = response_data.get("start", "")
            end_str = response_data.get("end", "")

            if not event_subject or not start_str or not end_str:
                return self.failed_result(
                    message="Missing subject/start/end",
                    code="missing_fields",
                )

            start = self._parse_datetime(start_str)
            end = self._parse_datetime(end_str)
            if not start or not end:
                return self.failed_result(
                    message="Invalid datetime format",
                    code="invalid_datetime",
                )

            entry_id = str(email_data.entry_id).strip()
            outlook_link = f"outlook:{entry_id}" if entry_id else ""

            row = {
                "email_subject": str(email_data.subject),
                "email_sender": str(email_data.sender),
                "email_received": str(email_data.received),
                "email_entry_id": entry_id,
                "outlook_link": outlook_link,
                "event_subject": str(event_subject),
                "start": start.isoformat(timespec="seconds"),
                "end": end.isoformat(timespec="seconds"),
                "location": str(response_data.get("location", "")),
                "body": str(response_data.get("body", "")),
                "logged_at": datetime.now().isoformat(timespec="seconds"),
            }

            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.exists() and output_path.stat().st_size > 0:
                workbook = load_workbook(output_path)
                worksheet = (
                    workbook["events"]
                    if "events" in workbook.sheetnames
                    else workbook.active
                )
            else:
                workbook = Workbook()
                worksheet = workbook.active
                worksheet.title = "events"

            if worksheet.max_row == 1 and worksheet.cell(1, 1).value is None:
                for column_index, field_name in enumerate(self.fields, start=1):
                    worksheet.cell(row=1, column=column_index, value=field_name)

            row_values = [row[field] for field in self.fields]
            worksheet.append(row_values)
            row_index = worksheet.max_row

            if outlook_link:
                link_col = self.fields.index("outlook_link") + 1
                link_cell = worksheet.cell(row=row_index, column=link_col)
                link_cell.value = "Open in Outlook"
                link_cell.hyperlink = outlook_link
                link_cell.style = "Hyperlink"

            workbook.save(output_path)

            return self.success_result(message="Event appended to Excel")
        except Exception as e:
            return self.retriable_failed_result(
                message=f"Unexpected error: {e}",
                code="unexpected_error",
            )

    def _parse_datetime(self, dt_str: str) -> datetime | None:
        """Parse ISO-like datetime string."""
        normalized = dt_str.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass

        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return None
