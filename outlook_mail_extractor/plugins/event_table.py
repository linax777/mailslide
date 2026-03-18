"""Event Table Plugin"""

import csv
from datetime import datetime
from pathlib import Path

from . import BasePlugin, PluginConfig, register_plugin


@register_plugin
class EventTablePlugin(BasePlugin):
    """Write extracted appointment data to a CSV table."""

    name = "event_table"
    default_system_prompt = """你是一個日曆助手。分析以下郵件內容，判斷是否包含預約、會議或行程資訊。

回覆時只輸出 JSON，不要有任何其他文字、解釋或 markdown 格式。"""
    default_response_json_format = {
        "create_true": '{"action": "appointment", "create": true, "subject": "約會主題", "start": "2024-01-15T14:00:00", "end": "2024-01-15T15:00:00", "location": "會議室或線上連結", "body": "額外備註"}',
        "create_false": '{"action": "appointment", "create": false}',
    }
    default_output_file = "output/events.csv"
    default_fields = [
        "email_subject",
        "email_sender",
        "email_received",
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
        self.fields = config.get("fields", self.default_fields)

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
    ) -> bool:
        """Write appointment data into CSV when LLM asks to create."""
        del outlook_client
        try:
            response_data = self._parse_response(llm_response)
            if response_data.get("action") != "appointment":
                return False

            if not response_data.get("create", False):
                return True

            event_subject = response_data.get("subject", "")
            start_str = response_data.get("start", "")
            end_str = response_data.get("end", "")

            if not event_subject or not start_str or not end_str:
                return False

            start = self._parse_datetime(start_str)
            end = self._parse_datetime(end_str)
            if not start or not end:
                return False

            row = {
                "email_subject": str(email_data.get("subject", "")),
                "email_sender": str(email_data.get("sender", "")),
                "email_received": str(email_data.get("received", "")),
                "event_subject": str(event_subject),
                "start": start.isoformat(timespec="seconds"),
                "end": end.isoformat(timespec="seconds"),
                "location": str(response_data.get("location", "")),
                "body": str(response_data.get("body", "")),
                "logged_at": datetime.now().isoformat(timespec="seconds"),
            }

            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not output_path.exists() or output_path.stat().st_size == 0

            with open(output_path, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=self.fields, extrasaction="ignore"
                )
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
            return True
        except Exception:
            return False

    def _parse_datetime(self, dt_str: str) -> datetime | None:
        """Parse ISO-like datetime string."""
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None
