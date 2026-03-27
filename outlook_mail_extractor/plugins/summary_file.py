"""Summary File Plugin"""

import csv
from datetime import datetime
from pathlib import Path

from ..models import EmailDTO, MailActionPort, PluginExecutionResult
from .base import BasePlugin, PluginCapability, PluginConfig, register_plugin


@register_plugin
class SummaryFilePlugin(BasePlugin):
    """Summarize email content with LLM and append results to CSV."""

    name = "summary_file"
    capabilities = {PluginCapability.REQUIRES_LLM}
    default_system_prompt = """你是郵件摘要助手。請根據郵件內容輸出精簡摘要。

回覆時只輸出 JSON，不要有任何其他文字、解釋或 markdown 格式。"""
    default_response_json_format = {
        "has_summary": '{"action": "summary", "summary": "2-5 句重點摘要", "priority": "high"}',
    }
    default_output_file = "output/email_summaries.csv"
    default_fields = [
        "email_subject",
        "email_sender",
        "email_received",
        "summary",
        "priority",
        "logged_at",
    ]

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = self._load_config(config)
        self.output_file = config.get("output_file", self.default_output_file)
        self.fields = list(self.default_fields)
        self._batch_flush_enabled = False
        self._pending_rows: list[dict[str, str]] = []

    def begin_job(self, context: dict | None = None) -> None:
        context = context or {}
        self._batch_flush_enabled = bool(context.get("batch_flush_enabled", False))
        self._pending_rows = []

    def end_job(self) -> PluginExecutionResult | None:
        if not self._batch_flush_enabled or not self._pending_rows:
            return None

        try:
            self._append_rows_to_csv(self._pending_rows)
            flushed_count = len(self._pending_rows)
            self._pending_rows = []
            return self.success_result(
                message=f"Flushed {flushed_count} buffered rows to CSV",
                code="batch_flushed",
                details={"flushed_rows": flushed_count},
            )
        except Exception as error:
            return self.retriable_failed_result(
                message=f"Batch flush failed: {error}",
                code="batch_flush_failed",
                details={"pending_rows": len(self._pending_rows)},
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
        """Append one summary row to CSV from LLM output."""
        del action_port
        try:
            response_data = self._parse_response(llm_response)
            action = response_data.get("action")
            if action and action != "summary":
                return self.skipped_result(
                    message="Action is not summary",
                    code="action_mismatch",
                )

            summary = str(response_data.get("summary", "")).strip()
            if not summary:
                return self.failed_result(
                    message="Missing summary",
                    code="missing_summary",
                )

            priority = str(response_data.get("priority", "")).strip().lower()
            if priority and priority not in {"high", "medium", "low"}:
                priority = ""

            row = {
                "email_subject": str(email_data.subject),
                "email_sender": str(email_data.sender),
                "email_received": str(email_data.received),
                "summary": summary,
                "priority": priority,
                "logged_at": datetime.now().isoformat(timespec="seconds"),
            }

            if self._batch_flush_enabled:
                self._pending_rows.append(row)
                return self.success_result(message="Summary buffered for batch flush")

            self._append_rows_to_csv([row])
            return self.success_result(
                message="Summary appended to CSV",
                details={"path": str(Path(self.output_file))},
            )
        except Exception as e:
            return self.retriable_failed_result(
                message=f"Unexpected error: {e}",
                code="unexpected_error",
            )

    def _append_rows_to_csv(self, rows: list[dict[str, str]]) -> None:
        if not rows:
            return

        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not output_path.exists() or output_path.stat().st_size == 0

        with open(output_path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fields, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerows(rows)
