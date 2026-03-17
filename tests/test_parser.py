"""Tests for email body parsing helpers."""

from outlook_mail_extractor.parser import clean_content, extract_main_content


def test_clean_content_keeps_forwarded_body_for_short_comment() -> None:
    """Keep the forwarded body when a forwarded email has only a short comment."""
    text = """
FYI

From: Alice <alice@example.com>
Sent: Tuesday, March 17, 2026 8:00 AM
To: Bob <bob@example.com>
Subject: Meeting notes

Here are the meeting notes.
- Item 1
- Item 2
"""

    result = clean_content(text, subject="FW: Meeting notes")

    assert "FYI" in result
    assert "Here are the meeting notes." in result
    assert "Item 1" in result


def test_clean_content_drops_reply_history_for_regular_reply() -> None:
    """Keep only the latest reply for non-forwarded conversations."""
    text = """
Looks good to me.

From: Alice <alice@example.com>
Sent: Tuesday, March 17, 2026 8:00 AM
To: Bob <bob@example.com>
Subject: Meeting notes

Here are the meeting notes.
"""

    result = clean_content(text, subject="Re: Meeting notes")

    assert result == "Looks good to me."


def test_extract_main_content_uses_subject_for_forward_detection() -> None:
    """Forward subject detection should work through extract_main_content."""
    plain_text = """
請參考

寄件者： Alice <alice@example.com>
收件者： Bob <bob@example.com>
主旨： 會議記錄

這是原始轉寄內容。
"""

    result = extract_main_content(plain_text=plain_text, subject="轉寄：會議記錄")

    assert "請參考" in result
    assert "這是原始轉寄內容。" in result
