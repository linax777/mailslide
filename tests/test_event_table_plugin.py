import asyncio
import csv
import json

from outlook_mail_extractor.models import (
    EmailDTO,
    PluginExecutionResult,
    PluginExecutionStatus,
)
from outlook_mail_extractor.plugins.event_table import EventTablePlugin


class _FakeActionPort:
    def move_to_folder(self, folder_name: str, create_if_missing: bool = True) -> None:
        del folder_name
        del create_if_missing

    def add_categories(self, categories: list[str]) -> None:
        del categories

    def create_appointment(self, *args, **kwargs) -> None:
        del args
        del kwargs


def _build_email_data() -> EmailDTO:
    return EmailDTO(
        subject="原始郵件主旨",
        sender="sender@example.com",
        received="2026-03-18 10:30:00",
        body="",
        tables=[],
    )


def test_event_table_writes_csv_row(tmp_path) -> None:
    output_file = tmp_path / "events.csv"
    plugin = EventTablePlugin(config={"output_file": str(output_file)})

    llm_response = json.dumps(
        {
            "action": "appointment",
            "create": True,
            "subject": "專案會議",
            "start": "2026-03-20T14:00:00",
            "end": "2026-03-20T15:00:00",
            "location": "Teams",
            "body": "討論里程碑",
        }
    )

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS
    assert result.success is True
    assert output_file.exists()

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    row = rows[0]
    assert row["email_subject"] == "原始郵件主旨"
    assert row["event_subject"] == "專案會議"
    assert row["start"] == "2026-03-20T14:00:00"
    assert row["end"] == "2026-03-20T15:00:00"
    assert row["location"] == "Teams"
    assert row["body"] == "討論里程碑"
    assert row["logged_at"]


def test_event_table_accepts_timezone_datetimes(tmp_path) -> None:
    output_file = tmp_path / "events.csv"
    plugin = EventTablePlugin(config={"output_file": str(output_file)})

    llm_response = json.dumps(
        {
            "action": "appointment",
            "create": True,
            "subject": "跨時區會議",
            "start": "2026-03-25T12:00:00+08:00",
            "end": "2026-03-25T13:30:00+08:00",
            "location": "Teams",
            "body": "含時區時間",
        }
    )

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    row = rows[0]
    assert row["start"] == "2026-03-25T12:00:00+08:00"
    assert row["end"] == "2026-03-25T13:30:00+08:00"


def test_event_table_noop_when_create_false(tmp_path) -> None:
    output_file = tmp_path / "events.csv"
    plugin = EventTablePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"appointment","create":false}'

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SKIPPED
    assert output_file.exists() is False


def test_event_table_appends_without_duplicate_header(tmp_path) -> None:
    output_file = tmp_path / "events.csv"
    plugin = EventTablePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"appointment","create":true,"subject":"A","start":"2026-03-20T09:00:00","end":"2026-03-20T10:00:00"}'

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


def test_event_table_ignores_custom_fields_config(tmp_path) -> None:
    output_file = tmp_path / "events.csv"
    plugin = EventTablePlugin(
        config={
            "output_file": str(output_file),
            "fields": ["custom_a", "custom_b"],
        }
    )
    llm_response = '{"action":"appointment","create":true,"subject":"A","start":"2026-03-20T09:00:00","end":"2026-03-20T10:00:00"}'

    result = asyncio.run(
        plugin.execute(_build_email_data(), llm_response, _FakeActionPort())
    )

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    assert rows[0] == [
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
