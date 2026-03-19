"""Write File Plugin"""

import json
import re
from datetime import datetime
from pathlib import Path

from ..models import PluginExecutionResult
from . import BasePlugin, PluginConfig, clean_invisible_chars, register_plugin


@register_plugin
class WriteFilePlugin(BasePlugin):
    """Write email data to JSON file"""

    name = "write_file"
    default_system_prompt = ""
    default_output_dir = "output"
    default_filename_format = "{subject}_{timestamp}"

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = self._load_config(config)
        self.output_dir = config.get("output_dir", self.default_output_dir)
        self.filename_format = config.get(
            "filename_format", self.default_filename_format
        )
        self.include_fields = config.get(
            "include_fields",
            ["subject", "sender", "received", "body", "tables"],
        )

    def _load_config(self, config: dict) -> PluginConfig:
        return PluginConfig(
            enabled=config.get("enabled", True),
            system_prompt=config.get("system_prompt", self.default_system_prompt),
            response_format=config.get("response_format", "json"),
            override_prompt=config.get("override_prompt"),
            response_json_format=config.get("response_json_format"),
        )

    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename"""
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        filename = re.sub(r"[\x00-\x1f]", "", filename)
        filename = filename[:200]
        filename = filename.rstrip(". ")
        return filename.strip("_") or "unnamed"

    def _prepare_email_data(self, email_data: dict) -> dict:
        """Filter and prepare email data for JSON output"""
        result = {}
        for key in self.include_fields:
            if key in email_data and key not in ("_message", "_account"):
                value = email_data[key]
                if isinstance(value, str):
                    value = value.strip()
                result[key] = value
        return clean_invisible_chars(result)

    async def execute(
        self,
        email_data: dict,
        llm_response: str,
        outlook_client=None,
    ) -> PluginExecutionResult:
        """Write email data to JSON file"""
        del llm_response
        del outlook_client
        try:
            output_path = Path(self.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            subject = email_data.get("subject", "unknown")
            safe_subject = self._sanitize_filename(subject)

            filename = self.filename_format.format(
                subject=safe_subject, timestamp=timestamp
            )
            filepath = output_path / f"{filename}.json"

            prepared_data = self._prepare_email_data(email_data)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(prepared_data, f, ensure_ascii=False, indent=2)

            return self.success_result(
                message="Email written to JSON file",
                details={"path": str(filepath)},
            )

        except Exception as e:
            return self.retriable_failed_result(
                message=f"Unexpected error: {e}",
                code="unexpected_error",
            )
