# Mailslide

專為 Windows + Outlook Classic 設計的郵件自動化工具。
用可配置流程與 LLM plugins，幫你把「看信、分類、彙整、後續處理」變成可重複執行的工作流。

Language: Traditional Chinese (`README.md`) | English (`README.en.md`)

## 為什麼是 Mailslide

- 把 Outlook 信件處理流程標準化：可建立多個 Job，固定規則執行。
- 不只分類：可移動資料夾、建立行事曆、輸出 JSON/CSV/Excel。
- LLM 可選：支援 OpenAI 相容 API，也可用本地模型（如 Ollama、llama.cpp）。
- 對非工程使用者友善：TUI 介面可直接初始化與編輯設定。

## 常見使用場景

- 行政/助理：自動整理通知信、會議信、待辦信。
- PM/業務：把客戶往來轉成可追蹤事件與摘要。
- 研發/客服：依主題或優先度自動分類，降低 inbox 噪音。

## 30 秒開始

```bash
uv sync
uv run app.py
```

接著在 TUI：

1. 進入 **About**，點 **初始化設定**。
2. 進入 **Configuration**，設定 Jobs / LLM / Plugins。
3. 回到 **Home** 執行 Job。

## 成果展示

- Home 執行與日誌：展示一次 Job 執行結果與處理統計
- Configuration 表單化設定：展示 Jobs / LLM / Plugins 設定頁
- Plugin 編輯器：展示 Prompt Profiles 與驗證/儲存流程

![Home Run](docs/assets/home-run.png)
![Configuration](docs/assets/configuration.png)
![Plugin Editor](docs/assets/plugin-editor.png)

## 插件能力對照

| 插件 | 主要用途 | 是否需要 LLM | 典型輸出 |
|---|---|---|---|
| `add_category` | 郵件分類並加標籤 | 是 | Outlook 分類標籤 |
| `move_to_folder` | 決定並移動資料夾 | 是 | 郵件移動結果 |
| `create_appointment` | 從郵件建立行事曆 | 是 | Outlook 行事曆項目 |
| `event_table` | 萃取活動資訊到表格 | 是 | `output/events.xlsx` |
| `summary_file` | 產生摘要與優先度 | 是 | `output/email_summaries.csv` |
| `write_file` | 匯出郵件原始資料 | 否 | `output/*.json` |

## 完整使用手冊

- 繁中：`GUIDE.md`
- English: `GUIDE.en.md`

`Guide` 分頁會優先顯示 `GUIDE.md` / `GUIDE.en.md`，找不到時才回退到 `README`。

## 系統需求

- Windows
- Outlook Classic（非 New Outlook）
- 執行期間 Outlook 需保持開啟

## 授權

`GPL-3.0-or-later`，詳見 `LICENSE`。
