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


def test_clean_content_strips_reply_headers_by_default() -> None:
    """Strip reply headers by default to keep only useful body content."""
    text = """
Looks good to me.

From: Alice <alice@example.com>
Sent: Tuesday, March 17, 2026 8:00 AM
To: Bob <bob@example.com>
Subject: Meeting notes

Here are the meeting notes.
"""

    result = clean_content(text, subject="Re: Meeting notes")

    assert "Looks good to me." in result
    assert "From: Alice <alice@example.com>" not in result
    assert "To: Bob <bob@example.com>" not in result
    assert "Subject: Meeting notes" not in result
    assert "Here are the meeting notes." in result


def test_clean_content_can_keep_reply_history_when_enabled() -> None:
    """Keep reply history content while still stripping metadata headers."""
    text = """
Looks good to me.

From: Alice <alice@example.com>
Sent: Tuesday, March 17, 2026 8:00 AM
To: Bob <bob@example.com>
Subject: Meeting notes

Here are the meeting notes.
"""

    result = clean_content(
        text,
        subject="Re: Meeting notes",
        preserve_reply_thread=True,
    )

    assert "Looks good to me." in result
    assert "Here are the meeting notes." in result
    assert "From: Alice <alice@example.com>" not in result
    assert "Sent: Tuesday, March 17, 2026 8:00 AM" not in result
    assert "To: Bob <bob@example.com>" not in result
    assert "Subject: Meeting notes" not in result


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


def test_clean_content_preserve_thread_strips_multilayer_metadata() -> None:
    """Keep thread body lines but remove repeated metadata headers."""
    text = """
Latest update

From : Alice <alice@example.com>
Sent : Tuesday, March 17, 2026 8:00 AM
To : Bob <bob@example.com>
Cc : Team <team@example.com>
Subject : Re: Project update

Prior message body A.

寄件者 ： Carol <carol@example.com>
已傳送 ： 2026/03/16 上午 10:30
收件人：Ops <ops@example.com>
副本(CC)：QA <qa@example.com>
主旨：專案更新

較舊內文 B。
"""

    result = clean_content(
        text,
        subject="Re: Project update",
        preserve_reply_thread=True,
    )

    assert "Latest update" in result
    assert "Prior message body A." in result
    assert "較舊內文 B。" in result
    assert "From : Alice <alice@example.com>" not in result
    assert "Sent : Tuesday, March 17, 2026 8:00 AM" not in result
    assert "To : Bob <bob@example.com>" not in result
    assert "Cc : Team <team@example.com>" not in result
    assert "Subject : Re: Project update" not in result
    assert "寄件者 ： Carol <carol@example.com>" not in result
    assert "已傳送 ： 2026/03/16 上午 10:30" not in result
    assert "收件人：Ops <ops@example.com>" not in result
    assert "副本(CC)：QA <qa@example.com>" not in result
    assert "主旨：專案更新" not in result


def test_clean_content_strips_date_header_variant() -> None:
    """Strip Date header variant from forwarded/replied blocks."""
    text = """
Quick note

Date: Tue, 17 Mar 2026 08:00:00 +0800
From: Alice <alice@example.com>
To: Bob <bob@example.com>
Subject: Notes

Body text
"""

    result = clean_content(text, subject="Re: Notes", preserve_reply_thread=True)

    assert "Quick note" in result
    assert "Body text" in result
    assert "Date: Tue, 17 Mar 2026 08:00:00 +0800" not in result
