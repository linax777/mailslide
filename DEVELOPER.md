# 開發者指南

## 專案架構

```
outlook-mail-extractor/
├── app.py                      # 應用程式入口 (Textual App)
├── config/
│   ├── config.yaml             # 主要設定 (jobs)
│   ├── config.yaml.sample      # 設定檔範本
│   ├── llm-config.yaml         # LLM API 設定
│   ├── llm-config.yaml.sample  # LLM 設定範本
│   ├── logging.yaml            # 日誌設定
│   └── plugins/                # 插件設定
├── logs/                      # 日誌輸出目錄
└── outlook_mail_extractor/
    ├── __init__.py
    ├── __main__.py             # CLI 入口點
    ├── config.py               # 設定檔載入與驗證
    ├── core.py                 # Outlook COM 連線與郵件處理
    ├── llm.py                  # LLM API 整合
    ├── logger.py               # 日誌管理
    ├── parser.py               # 郵件內容解析
    ├── models.py               # 資料模型
    ├── screens.py              # UI 畫面
    └── plugins/                # 插件系統
        ├── __init__.py
        ├── base.py
        ├── move.py
        ├── category.py
        └── calendar.py
```

## 技術棧

- **Textual** - TUI 框架
- **python-win32com** - Outlook COM 連線
- **PyYAML** - 設定檔解析
- **httpx** - HTTP 客戶端 (LLM API)
- **BeautifulSoup** - HTML 解析
- **pycron** - Cron 表達式解析
- **loguru** - 日誌記錄

## 執行方式

```bash
# TUI 應用程式
uv run python app.py

# CLI 模式
uv run outlook-extract --config config/config.yaml
```

## 程式碼規範

### Python 版本
- Python 3.13+ required
- 使用 `|` 聯合類型語法 (e.g., `str | None`)

### 命名慣例
- **Classes**: `PascalCase` (e.g., `OutlookClient`)
- **Functions/methods**: `snake_case` (e.g., `connect()`)
- **Private methods**: `_prefix` (e.g., `_perform_check()`)
- **Constants**: `UPPER_SNAKE_CASE`
- **Dataclass fields**: `snake_case`

### 引入順序

```python
# stdlib
from pathlib import Path
import re

# third-party
from bs4 import BeautifulSoup
from textual.app import App

# local
from outlook_mail_extractor.config import load_config
```

### Docstrings

使用 Google-style docstrings：

```python
def process_job(
    self,
    job_config: dict,
    dry_run: bool = False,
) -> list[dict]:
    """
    Process a single job configuration.

    Args:
        job_config: Dictionary with name, account, source, destination, limit
        dry_run: If True, don't actually move emails

    Returns:
        List of processed email data dictionaries

    Raises:
        FolderNotFoundError: When source/destination folder doesn't exist
    """
```

## 新增插件

1. 在 `outlook_mail_extractor/plugins/` 建立新檔案
2. 繼承 `BasePlugin` 類別
3. 使用 `@register_plugin` 裝飾器註冊

```python
from .base import BasePlugin, register_plugin

@register_plugin
class MyPlugin(BasePlugin):
    name = "my_plugin"
    default_system_prompt = "你的 system prompt..."

    async def execute(self, email_data, llm_response, outlook_client) -> bool:
        # 處理邏輯
        return True
```

## 日誌系統

每次執行會自動建立新的日誌檔案：

- **日誌目錄**：`logs/`
- **檔案命名**：`session_YYYYMMDD_HHMMSS.log`
- **滾動大小**：100MB
- **保留時間**：1 週
- **壓縮格式**：ZIP

### 即時日誌顯示

TUI 介面 Home 分頁會即時顯示日誌內容。實作要點：

1. **使用 `thread=True` 的 Worker**：
   ```python
   self.run_worker(self._execute_jobs(), exclusive=True, thread=True)
   ```

2. **UI Sink 回調需使用 `call_from_thread`**：
   ```python
   def ui_sink(message: str) -> None:
       self.app.call_from_thread(log_widget.write_line, message)
   ```

3. **Loguru 多重 Sink 配置**：
   ```python
   # File sink
   logger.add(log_file, level="DEBUG", format="...")

   # UI sink (仅 INFO+)
   logger.add(ui_sink_callback, level="INFO", format="...")
   ```

4. **避免重複創建 Session**：
   - 在 `screens.py` 中創建帶 UI sink 的 session
   - 在 `core.py` 中複用現有 session

## 執行測試與檢查

```bash
# 執行所有測試
uv run pytest

# 執行 lint
uv run ruff check .

# 類型檢查
uv run mypy .
```

## 按鍵快捷鍵

| 按鍵 | 功能 |
|------|------|
| `d` | 切換深色/淺色模式 |
| `q` | 結束應用程式 |
