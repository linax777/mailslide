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
        ├── calendar.py
        └── write_file.py
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
uv run app.py

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

### 基本結構

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

### LLM 與非 LLM 插件

插件透過 `default_system_prompt` 是否為空來區分是否需要 LLM：

| 類型 | `default_system_prompt` | 執行時機 |
|------|------------------------|----------|
| **需要 LLM** | 非空字串 | 先執行非 LLM 插件，再呼叫 LLM，最後執行 LLM 插件 |
| **不需要 LLM** | 空字串 `""` | 在 LLM 呼叫前先執行，傳入空的 `llm_response` |

**不需要 LLM 的插件示例** (`write_file.py`)：
```python
@register_plugin
class WriteFilePlugin(BasePlugin):
    name = "write_file"
    default_system_prompt = ""  # 空字串 = 不需要 LLM

    async def execute(self, email_data, llm_response, outlook_client=None) -> bool:
        # 直接使用 email_data，不依賴 LLM 回覆
        ...
```

**需要 LLM 的插件示例** (`category.py`)：
```python
@register_plugin
class AddCategoryPlugin(BasePlugin):
    name = "add_category"
    default_system_prompt = """你是一個郵件分類助手..."""

    async def execute(self, email_data, llm_response, outlook_client) -> bool:
        response_data = self._parse_response(llm_response)
        # 解析 LLM 回覆並執行動作
        ...
```

### PluginConfig 配置選項

| 選項 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `enabled` | `bool` | `True` | 是否啟用插件 |
| `system_prompt` | `str` | `default_system_prompt` | System prompt |
| `response_format` | `str` | `"json"` | LLM 回覆格式 |
| `override_prompt` | `str \| None` | `None` | 覆蓋 system prompt |
| `response_json_format` | `dict \| None` | `None` | JSON 格式範例 |

### response_json_format 使用方式

用於定義 LLM 回覆的 JSON 格式範例，自動附加到 system prompt：

```python
default_response_json_format = {
    "has_category": '{"action": "category", "categories": ["分類1"]}',
    "no_category": '{"action": "category", "categories": []}',
    "move": '{"action": "move", "folder": "資料夾名稱"}',
    "no_move": '{"action": "move", "folder": ""}',
    "create_true": '{"action": "appointment", "create": true, "subject": "主題", "start": "2024-01-15T14:00:00", "end": "2024-01-15T15:00:00"}',
    "create_false": '{"action": "appointment", "create": false}',
}
```

### 插件配置檔

在 `config/plugins/` 目錄下建立 `{plugin_name}.yaml`：

```yaml
# config/plugins/write_file.yaml
enabled: true
output_dir: "output"
filename_format: "{subject}_{timestamp}"
include_fields:
  - subject
  - sender
  - received
  - body
  - tables
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
