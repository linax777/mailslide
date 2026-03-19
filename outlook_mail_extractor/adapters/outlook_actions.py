"""Outlook-backed implementation of mail action port."""

from datetime import datetime

from ..models import MailActionPort


class OutlookMailActionAdapter(MailActionPort):
    """Perform mail side effects through Outlook COM client."""

    def __init__(self, client, message, account_name: str):
        self._client = client
        self._message = message
        self._account_name = account_name

    def move_to_folder(self, folder_name: str, create_if_missing: bool = True) -> None:
        """Move current message to target folder under current account."""
        destination = self._client.get_folder(
            self._account_name,
            folder_name,
            create_if_missing=create_if_missing,
        )
        self._message.Move(destination)

    def add_categories(self, categories: list[str]) -> None:
        """Append categories and save message."""
        existing = getattr(self._message, "Categories", "") or ""
        new_categories = ", ".join(categories)
        if existing:
            self._message.Categories = f"{existing}, {new_categories}"
        else:
            self._message.Categories = new_categories
        self._message.Save()

    def create_appointment(
        self,
        subject: str,
        start: datetime,
        end: datetime,
        location: str = "",
        body: str = "",
        recipients: list[str] | None = None,
    ) -> None:
        """Create appointment in current account's default calendar."""
        calendar = self._client.get_calendar_folder(self._account_name)
        appointment = calendar.Items.Add(1)  # 1 = olAppointmentItem
        appointment.Subject = subject
        appointment.Start = start
        appointment.End = end
        appointment.Location = location
        appointment.Body = body

        if recipients:
            for recipient_email in recipients:
                if recipient_email:
                    recipient = appointment.Recipients.Add(recipient_email)
                    recipient.Type = 1
                    recipient.Resolve()

        appointment.Save()
