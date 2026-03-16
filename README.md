# Outlook Mail Extractor

從 Outlook 提取郵件工具，支援 LLM 分析與自動化處理

## 命令列模式（CLI）

單次任務可直接使用 CLI 執行：

```bash
# 使用預設設定檔
uv run outlook-extract

# 指定自訂設定檔
uv run outlook-extract --config path/to/config.yaml

# 測試模式（僅讀取，不移動郵件）
uv run outlook-extract --dry-run

# 輸出結果至 JSON 檔案
uv run outlook-extract --output result.json

# 不移動郵件，僅擷取資料
uv run outlook-extract --no-move
```

## 如何設定 config.yaml

複製 `config/config.yaml.sample` 為 `config/config.yaml`，修改內容：

```yaml
jobs:
  - name: "我的工作"
    account: "your@email.com"
    source: "收件匣"
    destination: "收件匣/processed"
    limit: 10
    plugins:
      - add_category
```

| 設定項 | 說明 |
|--------|------|
| name | 工作名稱（隨意命名） |
| account | Outlook 帳號 Email |
| source | 來源資料夾（如「收件匣」） |
| destination | 處理後移動到（可省略） |
| limit | 處理的郵件數量 |
| plugins | 啟用的插件（可省略） |

## 設定 LLM（可選）

若要使用 plugins，需設定 `config/llm-config.yaml`：

```yaml
provider: "openai"
api_base: "http://localhost:11434/v1"
api_key: ""
model: "llama3"
```

支援 Ollama、LM Studio 等 OpenAI 相容 API。

## 內建插件

| 插件 | 功能 |
|------|------|
| add_category | AI 分析郵件並自動加上分類標籤 |
| move_to_folder | AI 判斷應該移動到哪個資料夾 |
| create_appointment | AI 分析郵件內容建立行事曆約會 |

## 圖形介面

執行 `uv run python app.py` 開啟 TUI 介面：

- **Home**：執行 Jobs、查看日誌
- **schedule**：設定自動排程
- **Guide**：使用說明
- **Configuration**：查看/編輯設定檔
- **About**：系統狀態檢查

## 需求

- Windows 作業系統
- Outlook Classic（不是 New Outlook）
- Outlook 必須在執行期間開啟
