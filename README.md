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

## 初始化設定

### 方法一：TUI 介面（推薦）

1. 執行 `uv run app.py`
2. 切換到 **About** 分頁（按 `A` 或點擊）
3. 點擊 **初始化設定** 按鈕
4. 程式會自動複製所有 `*.yaml.sample` 為 `*.yaml`

### 方法二：手動複製

```bash
# 主設定檔
copy config\config.yaml.sample config\config.yaml

# LLM 設定
copy config\llm-config.yaml.sample config\llm-config.yaml

# 日誌設定
copy config\logging.yaml.sample config\logging.yaml

# 插件設定
copy config\plugins\*.yaml.sample config\plugins\
```

> ⚠️ 初始化完成後，請務必打開各項設定檔，根據您的需求修改內容（如帳號、資料夾名稱、插件參數等）。

### 關於 `_ui` 區塊

`*.yaml.sample` 內含 `_ui` 區塊，描述未來 TUI 設定頁可用的欄位、按鈕與驗證規則（schema-driven UI）。

- `_ui` / `_meta` 為保留鍵，執行流程會忽略這些 UI 描述。
- 一般使用者只需要修改業務設定欄位（例如 `jobs`、`api_base`、`plugins`）。
- 進階開發可調整 `_ui` 來統一表單行為與驗證規格。

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

開啟 `config/config.yaml`，修改內容：

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
| enable | 是否啟用此工作（true/false，預設 true） |
| account | Outlook 帳號 Email 或資料檔案(pst)名稱 |
| source | 來源資料夾（如「收件匣」） |
| destination | 處理後移動到（可省略，若省略則郵件不會移動，可能重複處理，單純測試時可不加） |
| limit | 處理的郵件數量 |
| plugins | 啟用的插件（可省略） |

> 💡 提示：若使用 `move_to_folder` 插件讓 LLM 決定移動目錄，則可省略 `destination`，由插件負責移動。

## 設定 LLM（可選）

若要使用 plugins，需編輯 `config/llm-config.yaml`：

```yaml
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
| event_table | AI 分析郵件內容並將活動資訊追加到 CSV 表格 |
| write_file | 將郵件資料儲存為 JSON 檔案 |
| summary_file | AI 產生郵件摘要並追加到 CSV 表格 |

### write_file 插件設定

編輯 `config/plugins/write_file.yaml`：

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

### event_table 插件設定

編輯 `config/plugins/event_table.yaml`：

```yaml
enabled: true
output_file: "output/events.csv"   # 單一 CSV，逐筆 append
```

CSV 欄位由程式固定，順序為：
`email_subject`, `email_sender`, `email_received`, `event_subject`,
`start`, `end`, `location`, `body`, `logged_at`。

### summary_file 插件設定

編輯 `config/plugins/summary_file.yaml`：

```yaml
enabled: true
output_file: "output/email_summaries.csv"   # 單一 CSV，逐筆 append
```

CSV 欄位由程式固定，順序為：
`email_subject`, `email_sender`, `email_received`, `summary`, `priority`,
`logged_at`。

`summary_file` 的 LLM 回覆格式範例（不需要 `create` 欄位）：

```json
{
  "action": "summary",
  "summary": "這封信主要是確認合約版本與簽署時程，對方希望於本週五前回覆。",
  "priority": "high"
}
```

`priority` 欄位可省略；若提供，建議使用 `high`、`medium`、`low`。

## 圖形介面

> 💡 建議使用 PowerShell 執行本程式，以獲得更好的相容性與顯示效果。

執行 `uv run app.py` 開啟 TUI 介面：

| 按鍵 | 分頁 |
|------|------|
| `H` | Home：執行 Jobs、查看日誌 |
| `S` | Schedule：設定自動排程 |
| `G` | Guide：使用說明 |
| `C` | Configuration：查看/編輯設定檔 |
| `A` | About：系統狀態檢查、初始化設定 |

- **Home**：執行 Jobs、查看日誌
- **Schedule**：設定自動排程
- **Guide**：使用說明
- **Configuration**：查看/編輯設定檔
  - 一般設定：查看主設定檔與 Jobs 列表
  - LLM 設定：查看 LLM 設定值，可測試連線
  - Plugin 設定：可表單化編輯各 Plugin 設定（由 `config/plugins/*.yaml.sample` 的 `_ui` 欄位驅動）
- **About**：系統狀態檢查、初始化設定

### Plugin 設定（TUI）

在 **Configuration → Plugin 設定** 分頁中：

1. 選取 plugin
2. 點擊 **編輯設定**
3. 在 modal 內調整欄位並按 **驗證** 或 **儲存**

行為說明：

- 讀取優先順序：若 `config/plugins/<name>.yaml` 存在，會優先載入；否則使用 sample 預設。
- 驗證層級：先做欄位必填/型別/選項檢查，再套用 `_ui.validation_rules`。
- 安全寫檔：儲存前會移除 `_ui/_meta` 等保留鍵，並在覆蓋既有檔案前建立 `<name>.yaml.bak`。
- 回退機制：若 sample 缺少 `_ui`，此 plugin 會維持唯讀 YAML 檢視模式。
- `response_json_format` 編輯規則：`start`/`end`（以及 `action`）固定不可修改，其餘欄位可調整 value。

## 需求

- Windows 作業系統
- Outlook Classic（不是 New Outlook）
- Outlook 必須在執行期間開啟

## 本地 LLM（ llama.cpp）

本專案支援使用本地 LLM（如 llama.cpp），無需連接外部 API。

### 1. 下載 llama.cpp

從 [llama.cpp Releases](https://github.com/ggml-org/llama.cpp)，
下載 `llama-server.exe`（ Windows 版本，CPU 版本只適合小模型。)

### 2. 啟動 Server

推薦使用 qwen3.5 小模型，2B or 4B 對於郵件分類就有不錯的效果，
而且小模型也能使用 CPU 執行，Q8 量化占用約 2-4G RAM。
範例使用 Qwen3.5-2B-Q8_0.gguf (去 Hugginface 下載)

```powershell
# 基本啟動指令
.\llama-server.exe -m .\Qwen3.5-2B-Q8_0.gguf --port 8080

# 關閉思考功能（推薦）
.\llama-server.exe -m .\Qwen3.5-2B-Q8_0.gguf --port 8080 \
--chat_template_kwargs '{\"enable_thinking\":false}'
```

| 參數 | 說明 |
|------|------|
| `-m` | 模型檔案路徑 |
| `--port` | 伺服器連接埠（預設 8080） |
| `--chat_template_kwargs` | 額外參數，如關閉思考功能 |

### 3. 設定 config/llm-config.yaml

```yaml
api_base: "http://localhost:8080/v1"
api_key: "any"
model: "qwen3"
```

- `api_base`： llama.cpp server 的位址（須包含 `/v1`）
- `api_key`：任意字串（llama.cpp 不需要驗證）
- `model`：模型名稱（須與 GGUF 檔案對應）
