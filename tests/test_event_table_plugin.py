import asyncio
import csv
import json

from outlook_mail_extractor.plugins.event_table import EventTablePlugin


def _build_email_data() -> dict:
    return {
        "subject": "原始郵件主旨",
        "sender": "sender@example.com",
        "received": "2026-03-18 10:30:00",
    }


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

    success = asyncio.run(plugin.execute(_build_email_data(), llm_response, None))

    assert success is True
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


def test_event_table_noop_when_create_false(tmp_path) -> None:
    output_file = tmp_path / "events.csv"
    plugin = EventTablePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"appointment","create":false}'

    success = asyncio.run(plugin.execute(_build_email_data(), llm_response, None))

    assert success is True
    assert output_file.exists() is False


def test_event_table_appends_without_duplicate_header(tmp_path) -> None:
    output_file = tmp_path / "events.csv"
    plugin = EventTablePlugin(config={"output_file": str(output_file)})
    llm_response = '{"action":"appointment","create":true,"subject":"A","start":"2026-03-20T09:00:00","end":"2026-03-20T10:00:00"}'

    first = asyncio.run(plugin.execute(_build_email_data(), llm_response, None))
    second = asyncio.run(plugin.execute(_build_email_data(), llm_response, None))

    assert first is True
    assert second is True

    with open(output_file, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    assert len(rows) == 3
