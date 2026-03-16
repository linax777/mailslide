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
- **篩選條件**：靈活的郵件篩選配置

## 專案架構

```text
.
├── app.py                      # 應用程式入口 (Textual App)
├── config.yaml                 # 主要設定 (jobs)
├── config.yaml.sample          # 設定檔範本
├── llm.yaml                    # LLM API 設定
├── llm.yaml.sample             # LLM 設定範本
├── filters.yaml                # 郵件篩選條件
├── filters.yaml.sample         # 篩選條件範本
├── config/
│   └── plugins/               # 插件設定
│       ├── move_to_folder.yaml.sample
│       ├── add_category.yaml.sample
│       └── create_appointment.yaml.sample
│
└── outlook_mail_extractor/
    ├── __init__.py
    ├── config.py      # 設定檔載入與驗證
    ├── core.py        # Outlook COM 連線與郵件處理
    ├── llm.py         # LLM API 整合
    ├── parser.py      # 郵件內容解析
    ├── models.py      # 資料模型
    ├── screens.py    # UI 畫面
    └── plugins/      # 插件系統
        ├── __init__.py
        ├── base.py
        ├── move.py
        ├── category.py
        └── calendar.py
```

## 設定檔說明

### config.yaml - Jobs 設定

```yaml
jobs:
  - name: "處理會議郵件"
    account: "your@email.com"
    filter: "meeting_filter"    # 引用 filters.yaml 中的篩選條件
    plugins: ["move_to_folder", "add_category"]
    limit: 10
```

### llm.yaml - LLM API 設定

```yaml
provider: "openai"
api_base: "http://localhost:11434/v1"  # Ollama 預設端點
api_key: ""                               # 本地伺服器可留空
model: "llama3"
timeout: 30
```

### filters.yaml - 篩選條件

```yaml
meeting_filter:
  from_contains: "@company.com"
  subject_contains: ["meeting", "calendar", "invite"]
  is_unread: true
  limit: 10

bill_filter:
  from_contains: ["billing@service.com"]
  subject_contains: ["invoice", "bill"]
```

### 插件設定 (config/plugins/)

各插件可自訂 system prompt：

```yaml
enabled: true
system_prompt: |
  你的自訂 prompt...
response_format: "json"
```

## 內建插件

| 插件 | 功能 | LLM 回應格式 |
|------|------|--------------|
| `move_to_folder` | 移動郵件到指定資料夾 | `{"action": "move", "folder": "資料夾名稱"}` |
| `add_category` | 新增郵件分類標籤 | `{"action": "category", "categories": ["標籤1"]}` |
| `create_appointment` | 建立行事曆約會 | `{"action": "appointment", "create": true, ...}` |

## 開發指南

### 執行方式

```bash
# TUI 應用程式
uv run python app.py

# CLI 模式
uv run outlook-extract
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

### 新增篩選條件

在 `filters.yaml` 中定義新的篩選條件：

```yaml
my_filter:
  from_contains: "sender@example.com"
  subject_contains: ["關鍵字1", "關鍵字2"]
  is_unread: true
  importance: high
```

### 按鍵快捷鍵

| 按鍵 | 功能 |
|------|------|
| `d` | 切換深色/淺色模式 |
| `Ctrl+p` | 開啟命令面板 |

## 技術棧

- **Textual** - TUI 框架
- **python-win32com** - Outlook COM 連線
- **PyYAML** - 設定檔解析
- **httpx** - HTTP 客戶端 (LLM API)
- **BeautifulSoup** - HTML 解析

## 注意事項

- 僅支援 Windows + Outlook Classic (非 New Outlook)
- 執行時需開啟 Outlook 應用程式
- LLM 伺服器需支援 OpenAI 相容 API

---

## 開發建議事項

### 短期優化

1. **UI 增強**
   - 新增 LLM 分析狀態畫面，顯示處理進度
   - 新增日誌畫面，查看詳細執行紀錄
   - 支援設定檔編輯器

2. **錯誤處理**
   - 新增 LLM API 連線失敗的重試機制
   - 新增詳細的錯誤日誌

3. **測試**
   - 新增單元測試
   - 新增 Mock Outlook COM 物件的測試

### 中期規劃

1. **更多插件**
   - `forward_email` - 轉發郵件到指定地址
   - `extract_data` - 從郵件中結構化提取資料
   - `auto_reply` - 自動回覆郵件
   - `send_notification` - 處理完成後發送通知

2. **排程功能**
   - 支援定期自動執行 jobs
   - 新增排程設定檔

3. **Plugin 擴充**
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
