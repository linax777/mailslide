# Outlook Mail Extractor

從 Outlook 提取郵件工具，支援 LLM 分析與自動化處理

## 安裝 uv（必備）

本專案使用 [uv](https://github.com/astral-sh/uv) 管理 Python 依賴，請先安裝 uv：

```powershell
# PowerShell (Windows)
irm https://astral.sh/uv/install.ps1 | iex

# 或使用 pip
pip install uv

# 或使用 winget
winget install astral-sh.uv
```

## 安裝依賴

```bash
# 安裝專案依賴（同步模式）
uv sync
```

> ⚠️ 請務必使用 `uv sync` 而非 `uv pip install`，以確保依賴版本一致性。

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
| account | Outlook 帳號 Email 或資料檔案(pst)名稱 |
| source | 來源資料夾（如「收件匣」） |
| destination | 處理後移動到（可省略，若省略則郵件不會移動，可能重複處理） |
| limit | 處理的郵件數量 |
| plugins | 啟用的插件（可省略） |

> 💡 提示：若使用 `move_to_folder` 插件讓 LLM 決定移動目錄，則省略 `destination`，由插件負責移動。

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
| write_file | 將郵件資料儲存為 JSON 檔案 |

### write_file 插件設定

複製 `config/plugins/write_file.yaml.sample` 為 `config/plugins/write_file.yaml`：

```yaml
enabled: true
output_dir: "output"           # 輸出目錄
filename_format: "{subject}_{timestamp}"  # 檔名格式
include_fields:                # 要包含的欄位
  - subject
  - sender
  - received
  - body
  - tables
```

## 圖形介面

> 💡 建議使用 PowerShell 執行本程式，以獲得更好的相容性與顯示效果。

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
