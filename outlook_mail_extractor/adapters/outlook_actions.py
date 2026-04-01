"""Outlook-backed implementation of mail action port."""

from datetime import datetime
from pathlib import Path

from ..models import AttachmentDescriptor, MailActionPort


_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"
_PR_ATTACHMENT_HIDDEN = "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B"
_OL_EMBEDDED_ITEM = 5
_OL_OLE = 6


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

    def list_attachments(self) -> list[AttachmentDescriptor]:
        """List current message attachments in deterministic index order."""
        collection = getattr(self._message, "Attachments", None)
        if collection is None:
            return []

        count = int(getattr(collection, "Count", 0) or 0)
        descriptors: list[AttachmentDescriptor] = []
        for index in range(1, count + 1):
            attachment = collection.Item(index)
            filename = str(getattr(attachment, "FileName", "") or "")
            content_id = self._read_string_property(attachment, _PR_ATTACH_CONTENT_ID)
            has_content_id = bool(content_id.strip())

            hidden_flag = self._read_bool_property(attachment, _PR_ATTACHMENT_HIDDEN)
            attachment_type = self._read_int_attr(attachment, "Type")
            embedded_item_type = attachment_type in {_OL_EMBEDDED_ITEM, _OL_OLE}

            explicit_inline: bool | None
            if has_content_id:
                explicit_inline = True
            elif hidden_flag is True:
                explicit_inline = True
            elif embedded_item_type:
                explicit_inline = True
            elif hidden_flag is False:
                explicit_inline = False
            elif attachment_type is not None:
                explicit_inline = False
            else:
                explicit_inline = None

            metadata_complete = (
                has_content_id or hidden_flag is not None or attachment_type is not None
            )
            descriptors.append(
                AttachmentDescriptor(
                    index=index,
                    filename=filename,
                    explicit_inline=explicit_inline,
                    has_content_id=has_content_id,
                    hidden=hidden_flag,
                    embedded_item_type=embedded_item_type,
                    metadata_complete=metadata_complete,
                )
            )

        return descriptors

    def save_attachment(self, attachment_index: int, destination_path: Path) -> None:
        """Save one message attachment to destination path."""
        collection = getattr(self._message, "Attachments", None)
        if collection is None:
            raise RuntimeError("Current message has no attachments collection")

        attachment = collection.Item(int(attachment_index))
        attachment.SaveAsFile(str(destination_path))

    @staticmethod
    def _read_int_attr(attachment: object, attr_name: str) -> int | None:
        try:
            raw_value = getattr(attachment, attr_name)
        except Exception:
            return None

        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _read_string_property(attachment: object, property_name: str) -> str:
        accessor = getattr(attachment, "PropertyAccessor", None)
        if accessor is None:
            return ""

        try:
            raw = accessor.GetProperty(property_name)
        except Exception:
            return ""

        return str(raw or "")

    @staticmethod
    def _read_bool_property(attachment: object, property_name: str) -> bool | None:
        accessor = getattr(attachment, "PropertyAccessor", None)
        if accessor is None:
            return None

        try:
            raw = accessor.GetProperty(property_name)
        except Exception:
            return None

        if isinstance(raw, bool):
            return raw
        if raw in (0, 1):
            return bool(raw)
        return None
