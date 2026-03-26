# mailslide

從 Outlook 提取郵件工具，支援 LLM 分析與自動化處理

For the English version, see `README.en.md`.

## 30 秒快速上手（TUI）

```bash
uv sync
uv run app.py
```

1. 進入 **About** 分頁，點 **初始化設定**
2. 進入 **Configuration → 一般設定**，新增/調整 Jobs 後按 **驗證**、**儲存**
3. 需要 LLM 時，進入 **Configuration → LLM 設定** 調整參數並按 **測試連線**
4. 需要插件時，進入 **Configuration → Plugin 設定** 選取 plugin 後按 **編輯設定**

> 💡 建議：優先在 TUI 完成設定；手動編輯 YAML 僅作為進階備援方式。

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

> ⚠️ 初始化完成後，請務必依需求調整設定（如帳號、資料夾名稱、插件參數等）；建議直接在 TUI 的 **Configuration** 分頁修改。

## 推薦流程：直接在 TUI 修改設定

從目前版本開始，建議直接使用 **Configuration** 分頁完成大部分設定，不必手動開 YAML 檔案。

1. 執行 `uv run app.py`
2. 到 **About** 分頁按一次 **初始化設定**
3. 切到 **Configuration** 分頁：
   - **一般設定**：新增/刪除 Job、修改 `config.yaml`、驗證與儲存
   - **LLM 設定**：編輯 `llm-config.yaml`、測試連線
   - **Plugin 設定**：選 plugin 後以表單編輯 `config/plugins/*.yaml`

儲存保護機制（TUI）：

- 主設定儲存前會先做 schema 與 runtime 驗證，避免把不合法設定寫入。
- 覆蓋既有檔案前會建立備份（如 `config.yaml.bak`、`llm-config.yaml.bak`、`<plugin>.yaml.bak`）。

### 關於 `_ui` 區塊

`*.yaml.sample` 內含 `_ui` 區塊，描述未來 TUI 設定頁可用的欄位、按鈕與驗證規則（schema-driven UI）。

- `_ui` / `_meta` 為保留鍵，執行流程會忽略這些 UI 描述。
- 一般使用者只需要修改業務設定欄位（例如 `jobs`、`api_base`、`plugins`）。
- 進階開發可調整 `_ui` 來統一表單行為與驗證規格。
- `_ui` 的 `label_key` / `message_key` 可搭配 i18n key 做多語顯示；`label` / `message` 仍可作為 fallback。

## 命令列模式（CLI）

單次任務可直接使用 CLI 執行：

```bash
# 使用預設設定檔
uv run mailslide

# 指定自訂設定檔
uv run mailslide --config path/to/config.yaml

# 測試模式（僅讀取，不移動郵件）
uv run mailslide --dry-run

# 輸出結果至 JSON 檔案
uv run mailslide --output result.json

# 不移動郵件，僅擷取資料
uv run mailslide --no-move
```

## Python import 遷移

新的 import path 建議使用 `mailslide`：

```python
from mailslide import load_config, LLMClient
```

最小可執行範例：

```python
from pathlib import Path

from mailslide import load_config


config = load_config(Path("config/config.yaml"))
print(f"jobs: {len(config.get('jobs', []))}")
```

相容期內舊路徑 `outlook_mail_extractor` 仍可使用，但後續 major 版本將移除。

## 如何設定 config.yaml

可在 **Configuration → 一般設定** 直接修改（推薦）；也可手動編輯 `config/config.yaml`。

```yaml
llm_mode: per_plugin
plugin_modules:
  - custom_plugins.my_plugin_module

jobs:
  - name: "我的工作"
    account: "your@email.com"
    source: "收件匣"
    destination: "收件匣/processed"
    manual_review_destination: "收件匣/manual_review"
    batch_flush_enabled: true
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
| manual_review_destination | LLM 無 action（skipped）或失敗（failed/retriable_failed）時移動到人工判斷資料夾（可省略） |
| limit | 處理的郵件數量 |
| llm_mode | LLM 呼叫模式（`per_plugin` 預設；`share_deprecated` 為舊模式） |
| plugin_modules | 額外 plugin 模組路徑清單（啟動時動態 import，供註冊自訂 plugins） |
| ui_language | 介面語言（`zh-TW` / `en-US`，預設 `zh-TW`） |
| batch_flush_enabled | Job 級批次寫入開關（預設 `true`；影響 `event_table`/`summary_file`） |
| plugins | 啟用的插件（可省略） |

> 💡 提示：若使用 `move_to_folder` 插件讓 LLM 決定移動目錄，則可省略 `destination`，由插件負責移動。

### LLM 呼叫模式

- `per_plugin`（預設）：每個需要 LLM 的 plugin 各自呼叫一次 LLM，適合多 plugin 混用。
- `share_deprecated`（舊模式）：同一封郵件只呼叫一次 LLM，回覆共用給所有 LLM plugins。此模式容易因 `action` 不同造成 `action_mismatch/skipped`，不建議新設定使用。

`llm_mode` 可設在：

- 全域：`config.llm_mode`
- 單一 Job 覆蓋：`job.llm_mode`

> 向後相容：舊值 `shared` / `shared_legacy` 仍可執行，但會被視為 `share_deprecated` 並記錄警告。

## 多語言（gettext + Babel）

本專案採用 key-based i18n：程式使用翻譯 key（例如 `app.title`）而非直接寫死文案。

- 執行期：`gettext`（若未編譯 catalog，會 fallback 到 `outlook_mail_extractor/locales/*.yaml`）
- 開發期：`Babel` 管理 `po/mo`

CLI 可用 `--lang` 暫時覆蓋語言（`zh-TW` / `en-US`）：

```bash
uv run mailslide --lang en-US
```

或在 `config/config.yaml` 設定：

```yaml
ui_language: zh-TW
```

常用 Babel 指令（在專案根目錄執行）：

```bash
# 抽取可翻譯字串到 POT
pybabel extract -F babel.cfg -o outlook_mail_extractor/locales/gettext/messages.pot .

# 初始化語言（首次）
pybabel init -i outlook_mail_extractor/locales/gettext/messages.pot -d outlook_mail_extractor/locales/gettext -D messages -l zh_TW
pybabel init -i outlook_mail_extractor/locales/gettext/messages.pot -d outlook_mail_extractor/locales/gettext -D messages -l en_US

# 更新既有語言
pybabel update -i outlook_mail_extractor/locales/gettext/messages.pot -d outlook_mail_extractor/locales/gettext -D messages

# 編譯成 .mo
pybabel compile -d outlook_mail_extractor/locales/gettext -D messages
```

也可直接使用 PowerShell 腳本（Windows）：

```powershell
./scripts/i18n.ps1 all
# 或分步驟：extract / init / update / compile
```

## 設定 LLM（可選）

若要使用 plugins，建議在 **Configuration → LLM 設定** 編輯；也可手動修改 `config/llm-config.yaml`：

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
| event_table | AI 分析郵件內容並將活動資訊追加到 Excel 表格（含 Outlook 開信連結） |
| write_file | 將郵件資料儲存為 JSON 檔案 |
| summary_file | AI 產生郵件摘要並追加到 CSV 表格 |

### write_file 插件設定

建議在 **Configuration → Plugin 設定** 選取 `write_file` 後編輯；也可手動改 `config/plugins/write_file.yaml`：

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

建議在 **Configuration → Plugin 設定** 選取 `event_table` 後編輯；也可手動改 `config/plugins/event_table.yaml`：

```yaml
enabled: true
output_file: "output/events.xlsx"   # 單一 Excel，預設 job 級批次 flush
```

Excel 欄位由程式固定，順序為：
`email_subject`, `email_sender`, `email_received`, `email_entry_id`,
`outlook_link`, `event_subject`, `start`, `end`, `location`, `body`, `logged_at`。

- `email_entry_id`：Outlook 郵件 EntryID
- `outlook_link`：可直接點擊開啟 Outlook classic 對應郵件（`outlook:<EntryID>`）

> 備註：`outlook_link` 主要對 Outlook classic 生效；若郵件來源無法取得 `EntryID`，該欄位會留空。

若想回到逐筆即時寫入，可在對應 job 設定 `batch_flush_enabled: false`。

### summary_file 插件設定

建議在 **Configuration → Plugin 設定** 選取 `summary_file` 後編輯；也可手動改 `config/plugins/summary_file.yaml`：

```yaml
enabled: true
output_file: "output/email_summaries.csv"   # 單一 CSV，預設 job 級批次 flush
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

若想回到逐筆即時寫入，可在對應 job 設定 `batch_flush_enabled: false`。

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
| `L` | Language：切換介面語言（zh-TW / en-US） |

- **Home**：執行 Jobs、查看日誌
- **Schedule**：設定自動排程
- **Guide**：使用說明
- **Configuration**：查看/編輯設定檔
  - 一般設定：可直接新增/刪除 Job、編輯/驗證/儲存主設定
  - LLM 設定：可表單化編輯 LLM 設定並測試連線
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

### 同 Plugin 多 Prompt（Prompt Profiles）

同一個 plugin 可定義多組 system prompt（稱為「profile」），讓不同 Job 使用不同的 prompt：

目前內建支援 Prompt Profiles 的 LLM plugins：

- `add_category`
- `move_to_folder`
- `create_appointment`
- `event_table`
- `summary_file`

在 **Configuration → Plugin 設定 → 編輯設定** 中，以上 plugins 會顯示 `Prompt Profiles` 的 profile 列表（OptionList）與詳細欄位編輯器，可直接切換/新增/刪除 profile。

**1. Plugin 設定（`config/plugins/<name>.yaml.sample`）**

```yaml
# 定義多個 prompt profiles
default_prompt_profile: general_v1

prompt_profiles:
  general_v1:
    version: 1
    description: "一般分類"
    system_prompt: |
      你是一個郵件分類助手...

  invoice_v1:
    version: 1
    description: "帳單分類"
    system_prompt: |
      你是一個帳單分類助手，優先偵測付款語意...
```

**2. Job 設定（`config/config.yaml`）**

```yaml
jobs:
  - name: "處理一般郵件"
    plugins:
      - add_category
    # 不指定時使用 plugin 的 default_prompt_profile

  - name: "處理帳單"
    plugins:
      - add_category
    plugin_prompt_profiles:
      add_category: invoice_v1  # 指定使用 invoice_v1 profile
```

**解析優先序**

1. `job.plugin_prompt_profiles[plugin]` → 對應 profile 的 system_prompt
2. `plugin.default_prompt_profile` → 若 job 未指定，使用預設 profile
3. `plugin.system_prompt` → 完全無 profiles 時的 fallback

**命名規則**

- Profile key：`場景_v<major>`（如 `invoice_v1`、`vip_v2`）
- 每個 profile 內含 `version` 整數，方便日後追蹤遷移

## 需求

- Windows 作業系統
- Outlook Classic（不是 New Outlook）
- Outlook 必須在執行期間開啟

## 授權

本專案採用 `GPL-3.0-or-later` 授權，詳見 `LICENSE`。

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
