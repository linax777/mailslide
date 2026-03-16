# Outlook Mail Extractor

提取郵件內文工具，支援 LLM 分析與自動化處理

## 快速開始

```bash
# 安裝依賴
uv pip install -e .

# 執行應用程式
uv run python app.py
```

## 功能特色

- **郵件提取**：從 Outlook Classic 提取郵件內容
- **LLM 分析**：整合 OpenAI 相容 API (llama.cpp, Ollama, LM Studio 等) 分析郵件
- **插件系統**：可擴充的自動化處理插件
- **排程執行**：支援 cron 表達式定期執行
- **圖形介面**：直覺的 Textual TUI 介面
- **即時日誌**：執行時即時顯示日誌，並保存到日誌檔案

## 專案架構

```text
.
├── app.py                      # 應用程式入口 (Textual App)
├── config/
│   ├── config.yaml             # 主要設定 (jobs)
│   ├── config.yaml.sample      # 設定檔範本
│   ├── llm-config.yaml         # LLM API 設定
│   ├── llm-config.yaml.sample  # LLM 設定範本
│   ├── logging.yaml            # 日誌設定
│   └── plugins/               # 插件設定
│       ├── move_to_folder.yaml.sample
│       ├── add_category.yaml.sample
│       ├── create_appointment.yaml
│       └── create_appointment.yaml.sample
├── logs/                      # 日誌輸出目錄
└── outlook_mail_extractor/
    ├── __init__.py
    ├── __main__.py           # CLI 入口點
    ├── config.py             # 設定檔載入與驗證
    ├── core.py               # Outlook COM 連線與郵件處理
    ├── llm.py                # LLM API 整合
    ├── logger.py             # 日誌管理
    ├── parser.py              # 郵件內容解析
    ├── models.py              # 資料模型
    ├── screens.py             # UI 畫面
    └── plugins/              # 插件系統
        ├── __init__.py
        ├── base.py
        ├── move.py
        ├── category.py
        └── calendar.py
```

## 設定檔說明

### config/config.yaml - Jobs 設定

```yaml
jobs:
  - name: "處理microsoft郵件"
    account: "your@email.com"
    source: "收件匣/microsoft"                    # 來源資料夾
    destination: "收件匣/microsoft/processed"    # 目標資料夾 (自動移動)
    limit: 10                                      # 處理的郵件數量
    plugins:
      - add_category                               # LLM 分析插件
```

**重要**：
- `destination`：自動移動郵件到指定資料夾（無需 LLM）
- `plugins`：使用 LLM 分析處理（分類、加標籤等）
- **請勿**同時使用 `destination` 和 `move_to_folder` 插件，會造成衝突

### config/llm-config.yaml - LLM API 設定

```yaml
provider: "openai"
api_base: "http://localhost:11434/v1"  # Ollama 預設端點
api_key: ""                               # 本地伺服器可留空
model: "llama3"
timeout: 30
```

### 插件設定 (config/plugins/)

各插件可自訂 system prompt：

```yaml
enabled: true
system_prompt: |
  你的自訂 prompt...
response_format: "json"
```

## UI 分頁說明

| 分頁 | 功能 |
|------|------|
| Home | Jobs 列表、執行按鈕、日誌輸出 |
| 排程 | 排程開關、Cron 表達式設定 |
| About | 系統狀態檢查 (設定檔、Outlook 連線) |
| Configuration | 設定檔檢視 (一般、LLM、Plugins，含重新整理按鈕) |

### 排程功能

支援 cron 表達式：

| 表達式 | 意義 |
|--------|------|
| `0 * * * *` | 每小時整點 |
| `0 9 * * *` | 每天早上 9 點 |
| `0 9 * * 1-5` | 平日早上 9 點 |
| `*/15 * * * *` | 每 15 分鐘 |

**注意**：啟用排程前會自動驗證 cron 表達式格式，若格式錯誤會顯示通知並阻止啟用。

## 內建插件

| 插件 | 功能 | LLM 回應格式 |
|------|------|--------------|
| `move_to_folder` | 移動郵件到指定資料夾 | `{"action": "move", "folder": "資料夾名稱"}` |
| `add_category` | 新增郵件分類標籤 | `{"action": "category", "categories": ["標籤1"]}` |
| `create_appointment` | 建立行事曆約會 | `{"action": "appointment", "create": true, "subject": "主題", "start": "2024-01-15T14:00:00", "end": "2024-01-15T15:00:00", "location": "地點", "body": "備註"}`<br>可設定 `recipients` 自動加入與會者 |

## 開發指南

### 執行方式

```bash
# TUI 應用程式
uv run python app.py

# CLI 模式
uv run outlook-extract --config config/config.yaml
```

### 新增插件

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

### 按鍵快捷鍵

| 按鍵 | 功能 |
|------|------|
| `d` | 切換深色/淺色模式 |
| `q` | 結束應用程式 |

## 技術棧

- **Textual** - TUI 框架
- **python-win32com** - Outlook COM 連線
- **PyYAML** - 設定檔解析
- **httpx** - HTTP 客戶端 (LLM API)
- **BeautifulSoup** - HTML 解析
- **pycron** - Cron 表達式解析
- **loguru** - 日誌記錄

## 日誌系統

每次執行會自動建立新的日誌檔案：

- **日誌目錄**：`logs/`
- **檔案命名**：`session_YYYYMMDD_HHMMSS.log`
- **滾動大小**：100MB
- **保留時間**：1 週
- **壓縮格式**：ZIP

### 日誌設定 (config/logging.yaml)

```yaml
logging:
  # UI 顯示的最低級別 (DEBUG, INFO, WARNING, ERROR)
  display_level: "INFO"
```

### 即時日誌顯示 (重要)

TUI 介面 Home 分頁會即時顯示日誌內容。這是通過 loguru 的多重 sink 實現：

1. **File Sink** - 寫入日誌檔案（包含 DEBUG 等詳細資訊）
2. **UI Sink** - 即時寫入 Textual Log Widget（只顯示 INFO+）

#### 實作要點

1. **使用 `thread=True` 的 Worker**：
   ```python
   # 在獨立執行緒中運行 worker，讓 call_from_thread 能正常工作
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
   - 在 `core.py` 中複用現有 session（不要再次調用 `start_session()`）

## 開發注意事項

### 程式碼規範

- Python 3.13+ required
- 使用 `|` 聯合類型語法 (e.g., `str | None`)
- 88 字元行寬限制 (Black 相容)
- 所有 public 函數需有 Google-style docstring

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
from .models import CheckStatus
```

### 命名慣例

- **Classes**: `PascalCase` (e.g., `OutlookClient`)
- **Functions/methods**: `snake_case` (e.g., `connect()`)
- **Private methods**: `_prefix` (e.g., `_perform_check()`)
- **Constants**: `UPPER_SNAKE_CASE`
- **Dataclass fields**: `snake_case`

### 執行測試與檢查

```bash
# 執行所有測試
uv run pytest

# 執行 lint
uv run ruff check .

# 類型檢查
uv run mypy .
```

## 注意事項

- 僅支援 Windows + Outlook Classic (非 New Outlook)
- 執行時需開啟 Outlook 應用程式
- LLM 伺服器需支援 OpenAI 相容 API

---

## 開發建議事項

### 短期優化

1. **UI 增強**
   - 支援設定檔編輯器
   - ~~新增詳細的錯誤日誌~~ ✅ 已完成

2. **錯誤處理**
   - 新增 LLM API 連線失敗的重試機制
   - ~~新增詳細的錯誤日誌~~ ✅ 已完成

### 中期規劃

1. **更多插件**
   - `forward_email` - 轉發郵件到指定地址
   - `extract_data` - 從郵件中結構化提取資料
   - `auto_reply` - 自動回覆郵件
   - `send_notification` - 處理完成後發送通知

2. **Plugin 擴充**
   - Plugin 支援設定檔
   - Plugin 間共享狀態

### 長期願景

1. **Web 介面**
   - Flask/FastAPI Web API
   - 網頁管理介面
   - 即時狀態監控

2. **雲端部署**
   - Docker 支援
   - 支援無頭 Outlook (Exchange/Graph API)

3. **AI 增強**
   - 自定義分類模型
   - 語意搜尋
   - 郵件摘要生成
