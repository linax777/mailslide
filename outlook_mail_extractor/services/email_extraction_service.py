"""Email extraction helpers for Outlook messages."""

import re

from ..i18n import t
from ..logger import get_logger
from ..models import EmailDTO
from ..parser import clean_content, parse_email_html


class EmailExtractionService:
    """Build ``EmailDTO`` payloads from Outlook COM messages."""

    def __init__(self, *, preserve_reply_thread: bool = False, max_length: int = 800):
        self._preserve_reply_thread = preserve_reply_thread
        self._max_length = max_length

    def extract_email_data(self, message, max_length: int | None = None) -> EmailDTO:
        """Extract data from one Outlook message."""
        logger = get_logger()
        raw_body = str(message.Body) if getattr(message, "Body", None) else ""
        html_body = str(message.HTMLBody) if getattr(message, "HTMLBody", None) else ""
        subject = str(message.Subject) if getattr(message, "Subject", None) else ""
        parsed_html = parse_email_html(html_body, use_cache=True)
        clean_limit = max_length or self._max_length

        html_clean_body = clean_content(
            parsed_html.text,
            max_length=clean_limit,
            subject=subject,
            preserve_reply_thread=self._preserve_reply_thread,
        )
        plain_clean_body = clean_content(
            raw_body,
            max_length=clean_limit,
            subject=subject,
            preserve_reply_thread=self._preserve_reply_thread,
        )
        clean_body = (
            html_clean_body
            if len(html_clean_body) >= len(plain_clean_body)
            else plain_clean_body
        )
        logger.debug(
            t(
                "log.core.mail_body_cleaned",
                plain=len(raw_body),
                html=len(html_body),
                cleaned=len(clean_body),
            )
        )

        store_id = ""
        try:
            parent = getattr(message, "Parent", None)
            store_id = str(getattr(parent, "StoreID", ""))
        except Exception:
            store_id = ""

        internet_message_id = str(getattr(message, "InternetMessageID", "")).strip()
        if not internet_message_id:
            try:
                property_accessor = getattr(message, "PropertyAccessor", None)
                if property_accessor is not None:
                    internet_message_id = str(
                        property_accessor.GetProperty(
                            "http://schemas.microsoft.com/mapi/proptag/0x1035001F"
                        )
                    ).strip()
            except Exception:
                internet_message_id = ""

        if not internet_message_id:
            try:
                property_accessor = getattr(message, "PropertyAccessor", None)
                if property_accessor is not None:
                    transport_headers = str(
                        property_accessor.GetProperty(
                            "http://schemas.microsoft.com/mapi/proptag/0x007D001F"
                        )
                    )
                    match = re.search(
                        r"^Message-ID:\s*(.+)$",
                        transport_headers,
                        flags=re.IGNORECASE | re.MULTILINE,
                    )
                    if match:
                        internet_message_id = match.group(1).strip()
            except Exception:
                internet_message_id = ""

        return EmailDTO(
            subject=str(getattr(message, "Subject", "")),
            sender=str(
                message.SenderEmailAddress
                if hasattr(message, "SenderEmailAddress")
                else getattr(message, "SenderName", "")
            ),
            received=str(getattr(message, "ReceivedTime", "")),
            body=clean_body,
            tables=parsed_html.tables,
            entry_id=str(getattr(message, "EntryID", "")),
            store_id=store_id,
            internet_message_id=internet_message_id,
        )
