"""HTML 與文字解析工具模組"""

import re
from typing import Any

from bs4 import BeautifulSoup

REPLY_SEPARATOR_PATTERNS = [
    r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$",
    r"^\s*From:\s.+$",
    r"^\s*Sent:\s.+$",
    r"^\s*To:\s.+$",
    r"^\s*Subject:\s.+$",
    r"^\s*On .+ wrote:\s*$",
    r"^\s*寄件者[:：]\s*.+$",
    r"^\s*收件者[:：]\s*.+$",
    r"^\s*副本[:：]\s*.+$",
    r"^\s*主旨[:：]\s*.+$",
]

REPLY_HEADER_PATTERNS = [
    r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$",
    r"^\s*From:\s.+$",
    r"^\s*Sent:\s.+$",
    r"^\s*To:\s.+$",
    r"^\s*Cc:\s.+$",
    r"^\s*Subject:\s.+$",
    r"^\s*On .+ wrote:\s*$",
    r"^\s*寄件者[:：]\s*.+$",
    r"^\s*已傳送[:：]\s*.+$",
    r"^\s*收件者[:：]\s*.+$",
    r"^\s*副本[:：]\s*.+$",
    r"^\s*主旨[:：]\s*.+$",
]

FORWARD_SUBJECT_PATTERNS = [
    r"^\s*fw\s*:",
    r"^\s*fwd\s*:",
    r"^\s*轉寄\s*[:：]",
    r"^\s*轉發\s*[:：]",
]

BLOCK_TAGS = {"p", "div", "section", "article", "br", "li", "tr", "ul", "ol"}

SIGNATURE_START_PATTERNS = [
    r"^\s*--\s*$",
    r"^\s*best regards[,]?\s*$",
    r"^\s*regards[,]?\s*$",
    r"^\s*kind regards[,]?\s*$",
    r"^\s*thanks[,]?\s*$",
    r"^\s*thank you[,]?\s*$",
    r"^\s*cheers[,]?\s*$",
    r"^\s*sent from my iphone\s*$",
    r"^\s*sent from my ipad\s*$",
    r"^\s*sent from outlook for (ios|android)\s*$",
]

FOOTER_KEYWORDS = [
    "unsubscribe",
    "view in browser",
    "manage preferences",
    "privacy policy",
    "terms of use",
    "all rights reserved",
    "copyright",
    "email preferences",
    "update your preferences",
    "mailing address",
    "本郵件",
    "取消訂閱",
    "隱私權政策",
    "版權所有",
]


def clean_invisible_chars(obj: Any) -> Any:
    """
    遞迴移除常見的 Unicode 不可見字元

    Args:
        obj: 輸入物件（str、dict、list 或其他）

    Returns:
        清理後的物件
    """
    if isinstance(obj, str):
        return re.sub(r"[\u00a0\u200b-\u200f\ufeff\u202a-\u202e\u034f]", "", obj)
    elif isinstance(obj, dict):
        return {
            clean_invisible_chars(k): clean_invisible_chars(v) for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [clean_invisible_chars(i) for i in obj]
    return obj


def html_to_text(html: str) -> str:
    """
    Convert HTML email content into readable text while preserving paragraphs.

    Args:
        html: HTML body content

    Returns:
        Extracted plain text
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "head", "title", "meta", "noscript"]):
            tag.decompose()

        for tag in soup.find_all(style=True):
            style = tag.get("style", "").replace(" ", "").lower()
            if "display:none" in style or "visibility:hidden" in style:
                tag.decompose()

        for tag in soup.find_all(attrs={"aria-hidden": "true"}):
            tag.decompose()

        for tag_name in BLOCK_TAGS:
            for tag in soup.find_all(tag_name):
                if tag_name == "br":
                    tag.replace_with("\n")
                elif tag_name == "li":
                    tag.insert_before("\n- ")
                elif tag_name == "tr":
                    tag.insert_before("\n")
                    cells = tag.find_all(["th", "td"])
                    if cells:
                        row_text = " | ".join(cell.get_text(" ", strip=True) for cell in cells)
                        tag.replace_with(f"{row_text}\n")
                else:
                    tag.insert_before("\n")
                    tag.insert_after("\n")

        return soup.get_text(" ", strip=False)
    except Exception:
        return ""


def normalize_text(text: str) -> str:
    """
    Normalize whitespace while preserving paragraphs.

    Args:
        text: Raw extracted text

    Returns:
        Normalized text
    """
    if not text:
        return ""

    text = clean_invisible_chars(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_reply_thread(text: str) -> str:
    """
    Remove quoted reply / forward history from email text.

    Args:
        text: Normalized email text

    Returns:
        Current-message focused text
    """
    if not text:
        return ""

    lines = text.splitlines()
    kept_lines: list[str] = []

    for line in lines:
        if any(re.match(pattern, line, re.IGNORECASE) for pattern in REPLY_SEPARATOR_PATTERNS):
            break
        kept_lines.append(line)

    return "\n".join(kept_lines).strip()


def is_forward_subject(subject: str) -> bool:
    """
    Check whether the email subject indicates a forwarded message.

    Args:
        subject: Email subject

    Returns:
        True when subject starts with a forward prefix
    """
    if not subject:
        return False

    return any(
        re.match(pattern, subject, re.IGNORECASE)
        for pattern in FORWARD_SUBJECT_PATTERNS
    )


def _find_reply_separator_index(lines: list[str]) -> int | None:
    """Find the first reply or forward separator line index."""
    for index, line in enumerate(lines):
        if any(re.match(pattern, line, re.IGNORECASE) for pattern in REPLY_SEPARATOR_PATTERNS):
            return index
    return None


def _is_short_forward_comment(text: str) -> bool:
    """Heuristically identify a short forwarded-message comment."""
    if not text:
        return False

    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return False

    if len(non_empty_lines) > 2:
        return False

    return len(" ".join(non_empty_lines)) <= 40


def _extract_forwarded_body(lines: list[str], separator_index: int) -> str:
    """Extract the body after a forwarded-message header block."""
    body_start = separator_index

    while body_start < len(lines) and lines[body_start].strip():
        body_start += 1

    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    return "\n".join(lines[body_start:]).strip()


def strip_reply_thread_with_subject(text: str, subject: str = "") -> str:
    """
    Remove reply history while preserving forwarded content when appropriate.

    Args:
        text: Normalized email text
        subject: Email subject used to detect forwarded messages

    Returns:
        Current-message focused text
    """
    if not text:
        return ""

    lines = text.splitlines()
    separator_index = _find_reply_separator_index(lines)
    if separator_index is None:
        return text.strip()

    comment = "\n".join(lines[:separator_index]).strip()
    if is_forward_subject(subject) and _is_short_forward_comment(comment):
        forwarded_body = _extract_forwarded_body(lines, separator_index)
        if forwarded_body:
            if comment:
                return f"{comment}\n\n{forwarded_body}".strip()
            return forwarded_body

    return comment


def strip_signature(text: str) -> str:
    """
    Remove high-confidence signature blocks from the tail of an email.

    Args:
        text: Email text without reply history

    Returns:
        Text with signature block removed when detected
    """
    if not text:
        return ""

    lines = text.splitlines()
    for index, line in enumerate(lines):
        if any(re.match(pattern, line, re.IGNORECASE) for pattern in SIGNATURE_START_PATTERNS):
            remaining = [value for value in lines[index:] if value.strip()]
            if 1 <= len(remaining) <= 12:
                return "\n".join(lines[:index]).strip()

    return text


def strip_reply_headers(text: str) -> str:
    """
    Remove reply/forward metadata header lines from body text.

    Args:
        text: Email text after optional thread trimming

    Returns:
        Text with reply header lines removed
    """
    if not text:
        return ""

    cleaned_lines = [
        line
        for line in text.splitlines()
        if not any(
            re.match(pattern, line, re.IGNORECASE) for pattern in REPLY_HEADER_PATTERNS
        )
    ]
    return "\n".join(cleaned_lines).strip()


def _is_footer_line(line: str) -> bool:
    candidate = line.strip().lower()
    if not candidate:
        return False
    return any(keyword in candidate for keyword in FOOTER_KEYWORDS)


def strip_footer(text: str) -> str:
    """
    Remove high-confidence newsletter or legal footer blocks.

    Args:
        text: Email text after reply/signature cleanup

    Returns:
        Text with footer-like tail removed when detected
    """
    if not text:
        return ""

    lines = text.splitlines()
    footer_start: int | None = None

    for index, line in enumerate(lines):
        if _is_footer_line(line):
            footer_start = index
            break

    if footer_start is None:
        return text

    tail_lines = lines[footer_start:]
    keyword_hits = sum(1 for line in tail_lines if _is_footer_line(line))
    non_empty_tail = sum(1 for line in tail_lines if line.strip())

    if keyword_hits >= 2 or (keyword_hits >= 1 and non_empty_tail <= 8):
        return "\n".join(lines[:footer_start]).strip()

    return text


def clean_content(
    text: str,
    max_length: int = 800,
    subject: str = "",
    preserve_reply_thread: bool = True,
) -> str:
    """
    清理郵件雜訊並保留段落結構。

    Args:
        text: 原始文字內容
        max_length: 最大輸出長度，預設 800
        subject: 郵件主旨，用於判斷是否為轉寄郵件
        preserve_reply_thread: 是否保留 RE/FW 原始對話內容，預設 True

    Returns:
        清理後的文字
    """
    if not text:
        return ""

    text = normalize_text(text)
    if not preserve_reply_thread:
        text = strip_reply_thread_with_subject(text, subject=subject)
    text = strip_reply_headers(text)
    text = strip_signature(text)
    text = strip_footer(text)

    # 移除網址
    text = re.sub(r"http[s]?://\S+", "[URL]", text)

    # 移除長度超過 20 的純隨機英數字串 (常見於追蹤碼或加密片段)
    text = re.sub(r"\b\w{20,}\b", "", text)

    # 重新整理清理後的段落與空白
    text = normalize_text(text)
    return text[:max_length]


def extract_main_content(
    plain_text: str = "",
    html: str = "",
    max_length: int = 800,
    subject: str = "",
    preserve_reply_thread: bool = True,
) -> str:
    """
    Extract the best available email body for downstream LLM processing.

    Args:
        plain_text: Outlook plain text body
        html: Outlook HTML body
        max_length: Maximum output length
        subject: Email subject
        preserve_reply_thread: Whether to keep RE/FW thread content

    Returns:
        Cleaned email body text
    """
    html_text = clean_content(
        html_to_text(html),
        max_length=max_length,
        subject=subject,
        preserve_reply_thread=preserve_reply_thread,
    )
    plain = clean_content(
        plain_text,
        max_length=max_length,
        subject=subject,
        preserve_reply_thread=preserve_reply_thread,
    )

    if len(html_text) >= len(plain):
        return html_text
    return plain


def parse_tables(html: str) -> list[list[dict]]:
    """
    解析 HTML 中的表格資料

    Args:
        html: HTML 內容

    Returns:
        表格資料列表，每個表格為一個列表包含多個字典
    """
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue
            headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
            # 過濾掉寬度過大的空標頭雜訊
            headers = [h if h else f"Col_{i}" for i, h in enumerate(headers)]

            data = []
            for r in rows[1:]:
                cells = r.find_all("td")
                if len(cells) == len(headers):
                    row_dict = dict(
                        zip(headers, [td.get_text(strip=True) for td in cells])
                    )
                    # 過濾：如果整列都是空值則不加入
                    if any(row_dict.values()):
                        data.append(row_dict)

            if data:
                results.append(data)
        return results
    except Exception:
        return []
