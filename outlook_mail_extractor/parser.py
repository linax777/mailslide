"""HTML 與文字解析工具模組"""

import re
from typing import Any

from bs4 import BeautifulSoup


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


def clean_content(text: str, max_length: int = 800) -> str:
    """
    清理郵件雜訊：移除網址、長串隨機字元及 Base64 編碼

    Args:
        text: 原始文字內容
        max_length: 最大輸出長度，預設 800

    Returns:
        清理後的文字
    """
    if not text:
        return ""
    # 0. 移除隱藏字元
    text = re.sub(r"[\u200b-\u200f\ufeff\u202a-\u202e\r]", "", text)
    # 1. 移除網址
    text = re.sub(r"http[s]?://\S+", "[URL]", text)
    # 2. 移除長度超過 20 的純隨機英數字串 (常見於追蹤碼或加密片段)
    text = re.sub(r"\b\w{20,}\b", "", text)
    # 3. 清理多餘換行與空白
    text = " ".join(text.split())
    return text[:max_length]


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
