# Mailslide

專為 Windows + Outlook Classic 設計的郵件自動化工具。
用可配置流程與 LLM plugins，幫你把「看信、分類、彙整、後續處理」變成可重複執行的工作流。

Language: [Traditional Chinese](README.zh-TW.md) | [English](README.md)

> 警語：AI 會閱讀你的郵件，請確認要讓 AI 處理的郵件不包含個人隱私或業務機密，或使用本地模型處理。
>
> 免責聲明：本專案僅提供工具，不保證第三方或本地 AI 模型處理資料之安全性；因使用者輸入內容或模型服務造成之資料外洩、機密洩漏或相關損害，專案作者不負任何責任。使用前請自行評估風險並遵循組織政策與法規。

## 為什麼是 Mailslide

- 把 Outlook 信件處理流程標準化：可建立多個 Job，固定規則執行。
- 不只分類：可移動資料夾、建立行事曆、輸出 JSON/CSV/Excel。
- LLM 可選：支援 OpenAI 相容 API，也可用本地模型（如 Ollama、llama.cpp）。
- 對非工程使用者友善：TUI 介面可直接初始化與編輯設定。

## 常見使用場景

- 行政/助理：自動整理通知信、會議信、待辦信。
- PM/業務：把客戶往來轉成可追蹤事件與摘要。
- 研發/客服：依主題或優先度自動分類，降低 inbox 噪音。

## 30 秒開始（一般使用者）

```bash
uv tool install mailslide
mailslide-tui
```

首次啟動後，進入 **About**，點 **初始化設定**。

升級：

```bash
uv tool upgrade mailslide
```

若新版調整 `config` 結構，程式載入時會自動遷移 `config/config.yaml`，並寫入時間戳備份（例如：`config.yaml.bak.20260327_153000`）。

## 30 秒開始（開發者 / 原始碼模式）

```bash
uv sync
uv run app.py
```

接著在 TUI：

1. 進入 **About**，點 **初始化設定**。
2. 進入 **Configuration**，設定 Jobs / LLM / Plugins。
3. 回到 **Home** 執行 Job（`保留 RE/FW` 預設為 `ON`，可在 Home 直接切換）。

## 截圖

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
