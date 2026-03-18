import asyncio
import json
from datetime import datetime

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


class _FakeOutlookClient:
    def __init__(self, calendar: _FakeCalendar) -> None:
        self._calendar = calendar

    def get_calendar_folder(self, _account: str) -> _FakeCalendar:
        return self._calendar


def test_create_appointment_accepts_timezone_datetime() -> None:
    plugin = CreateAppointmentPlugin()
    parsed = plugin._parse_datetime("2026-03-25T12:00:00+08:00")

    expected = datetime.fromisoformat("2026-03-25T12:00:00+08:00")
    expected = expected.astimezone().replace(tzinfo=None)

    assert parsed == expected


def test_create_appointment_execute_with_timezone_datetime() -> None:
    plugin = CreateAppointmentPlugin()
    calendar = _FakeCalendar()
    outlook_client = _FakeOutlookClient(calendar)
    email_data = {"_account": "user@example.com"}

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

    success = asyncio.run(plugin.execute(email_data, llm_response, outlook_client))

    assert success is True
    appointment = calendar.Items.last_appointment
    assert appointment is not None
    assert appointment.saved is True
    assert appointment.Start is not None
    assert appointment.End is not None
    assert appointment.Start.tzinfo is None
    assert appointment.End.tzinfo is None
