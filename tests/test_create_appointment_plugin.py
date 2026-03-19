import asyncio
import json
from datetime import datetime

from outlook_mail_extractor.models import (
    EmailDTO,
    PluginExecutionResult,
    PluginExecutionStatus,
)
from outlook_mail_extractor.plugins.calendar import CreateAppointmentPlugin


class _FakeRecipient:
    def __init__(self) -> None:
        self.Type = 0

    def Resolve(self) -> None:
        return None


class _FakeRecipients:
    def __init__(self) -> None:
        self.items: list[_FakeRecipient] = []

    def Add(self, _email: str) -> _FakeRecipient:
        recipient = _FakeRecipient()
        self.items.append(recipient)
        return recipient


class _FakeAppointment:
    def __init__(self) -> None:
        self.Subject = ""
        self.Start: datetime | None = None
        self.End: datetime | None = None
        self.Location = ""
        self.Body = ""
        self.Recipients = _FakeRecipients()
        self.saved = False

    def Save(self) -> None:
        self.saved = True


class _FakeItems:
    def __init__(self) -> None:
        self.last_appointment: _FakeAppointment | None = None

    def Add(self, _item_type: int) -> _FakeAppointment:
        appointment = _FakeAppointment()
        self.last_appointment = appointment
        return appointment


class _FakeCalendar:
    def __init__(self) -> None:
        self.Items = _FakeItems()


class _FakeActionPort:
    def __init__(self, calendar: _FakeCalendar) -> None:
        self._calendar = calendar

    def move_to_folder(self, folder_name: str, create_if_missing: bool = True) -> None:
        del folder_name
        del create_if_missing

    def add_categories(self, categories: list[str]) -> None:
        del categories

    def create_appointment(
        self,
        subject: str,
        start: datetime,
        end: datetime,
        location: str = "",
        body: str = "",
        recipients: list[str] | None = None,
    ) -> None:
        appointment = self._calendar.Items.Add(1)
        appointment.Subject = subject
        appointment.Start = start
        appointment.End = end
        appointment.Location = location
        appointment.Body = body
        if recipients:
            for email in recipients:
                recipient = appointment.Recipients.Add(email)
                recipient.Type = 1
                recipient.Resolve()
        appointment.Save()


def test_create_appointment_accepts_timezone_datetime() -> None:
    plugin = CreateAppointmentPlugin()
    parsed = plugin._parse_datetime("2026-03-25T12:00:00+08:00")

    expected = datetime.fromisoformat("2026-03-25T12:00:00+08:00")
    expected = expected.astimezone().replace(tzinfo=None)

    assert parsed == expected


def test_create_appointment_execute_with_timezone_datetime() -> None:
    plugin = CreateAppointmentPlugin()
    calendar = _FakeCalendar()
    action_port = _FakeActionPort(calendar)
    email_data = EmailDTO(
        subject="",
        sender="",
        received="",
        body="",
        tables=[],
    )

    llm_response = json.dumps(
        {
            "action": "appointment",
            "create": True,
            "subject": "跨時區會議",
            "start": "2026-03-25T12:00:00+08:00",
            "end": "2026-03-25T13:30:00+08:00",
            "location": "Teams",
            "body": "測試內容",
        }
    )

    result = asyncio.run(plugin.execute(email_data, llm_response, action_port))

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS
    assert result.success is True
    appointment = calendar.Items.last_appointment
    assert appointment is not None
    assert appointment.saved is True
    assert appointment.Start is not None
    assert appointment.End is not None
    assert appointment.Start.tzinfo is None
    assert appointment.End.tzinfo is None


def test_create_appointment_skip_hook_returns_skipped_result() -> None:
    plugin = CreateAppointmentPlugin()
    llm_response = json.dumps({"action": "appointment", "create": False})

    result = plugin.should_skip_by_response(llm_response)

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SKIPPED
    assert result.code == "llm_skip_condition"
