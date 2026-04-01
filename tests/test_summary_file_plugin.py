import asyncio
import csv
import json
from pathlib import Path

from outlook_mail_extractor.models import (
    AttachmentDescriptor,
    EmailDTO,
    PluginExecutionResult,
    PluginExecutionStatus,
)
from outlook_mail_extractor.plugins.summary_file import SummaryFilePlugin


class _FakeActionPort:
    def move_to_folder(self, folder_name: str, create_if_missing: bool = True) -> None:
        del folder_name
        del create_if_missing

    def add_categories(self, categories: list[str]) -> None:
        del categories

    def create_appointment(self, *args, **kwargs) -> None:
        del args
        del kwargs

    def list_attachments(self) -> list[AttachmentDescriptor]:
        return []

    def save_attachment(self, attachment_index: int, destination_path: Path) -> None:
        del attachment_index
        del destination_path


def _build_email_data() -> EmailDTO:
    return EmailDTO(
        subject="原始郵件主旨",
        sender="sender@example.com",
        received="2026-03-19 12:00:00",
        body="",
        tables=[],
    )


def test_summary_file_writes_csv_row(tmp_path) -> None:
    output_file = tmp_path / "summaries.csv"
    plugin = SummaryFilePlugin(config={"output_file": str(output_file)})

    llm_response = json.dumps(
        {
            "action": "summary",
            "summary": "這封信是客戶詢問報價，要求本週內回覆。",
            "priority": "high",
        }
    )

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS
    assert output_file.exists()
    assert result.details.get("path") == str(output_file)

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    row = rows[0]
    assert row["email_subject"] == "原始郵件主旨"
    assert row["summary"] == "這封信是客戶詢問報價，要求本週內回覆。"
    assert row["priority"] == "high"
    assert row["logged_at"]


def test_summary_file_writes_even_without_create_flag(tmp_path) -> None:
    output_file = tmp_path / "summaries.csv"
    plugin = SummaryFilePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"summary","summary":"只要產出摘要即可"}'

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS
    assert output_file.exists()


def test_summary_file_fails_when_summary_missing(tmp_path) -> None:
    output_file = tmp_path / "summaries.csv"
    plugin = SummaryFilePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"summary","summary":""}'

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.FAILED
    assert result.code == "missing_summary"
    assert output_file.exists() is False


def test_summary_file_appends_without_duplicate_header(tmp_path) -> None:
    output_file = tmp_path / "summaries.csv"
    plugin = SummaryFilePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"summary","summary":"A","priority":"medium"}'

    first = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )
    second = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(first, PluginExecutionResult)
    assert isinstance(second, PluginExecutionResult)
    assert first.status == PluginExecutionStatus.SUCCESS
    assert second.status == PluginExecutionStatus.SUCCESS

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    assert len(rows) == 3


def test_summary_file_normalizes_invalid_priority(tmp_path) -> None:
    output_file = tmp_path / "summaries.csv"
    plugin = SummaryFilePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"summary","summary":"A","priority":"urgent"}'

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["priority"] == ""


def test_summary_file_skips_when_action_mismatch(tmp_path) -> None:
    output_file = tmp_path / "summaries.csv"
    plugin = SummaryFilePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"category","summary":"A"}'

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SKIPPED
    assert result.code == "action_mismatch"
    assert output_file.exists() is False


def test_summary_file_batch_flush_writes_rows_on_end_job(tmp_path) -> None:
    output_file = tmp_path / "summaries.csv"
    plugin = SummaryFilePlugin(config={"output_file": str(output_file)})
    plugin.begin_job({"batch_flush_enabled": True})

    llm_response = '{"action":"summary","summary":"A","priority":"high"}'
    first = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )
    second = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert first.status == PluginExecutionStatus.SUCCESS
    assert second.status == PluginExecutionStatus.SUCCESS
    assert output_file.exists() is False

    flush_result = plugin.end_job()

    assert isinstance(flush_result, PluginExecutionResult)
    assert flush_result.status == PluginExecutionStatus.SUCCESS
    assert output_file.exists()

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 3
