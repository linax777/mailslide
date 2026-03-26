# Import Path Rename 評估（`outlook_mail_extractor` -> `mailslide`）

## 結論（先講）

- **建議先不要立即改 Python import path**，先維持 `outlook_mail_extractor` 作為程式碼 package 名稱。
- 目前已完成的品牌/CLI 更名（`mailslide`）已足夠對外一致；import path 更名屬於高風險、低即時收益改動。
- 若仍要改，建議走 **兩階段遷移**：先加相容層，再在下一個 major 版本移除舊路徑。

## 現況盤點

- Python 程式碼中 `outlook_mail_extractor` 參考約 **49 處**（主要在 `tests/*.py`、`app.py`）。
- 文件/設定腳本中相關字串約 **25 處**（`README*`、`pyproject.toml`、`scripts/i18n.ps1`、`CHANGELOG.md`）。
- 打包設定仍以舊 package 名稱為核心：
  - `pyproject.toml` 的 `project.scripts` 指向 `outlook_mail_extractor.__main__:main`
  - `tool.setuptools.packages.find.include = ["outlook_mail_extractor*"]`
  - `tool.setuptools.package-data` key 為 `outlook_mail_extractor`

## 變更影響面

1. **原始碼/測試**
   - 幾乎所有測試 import 需要改路徑。
   - `app.py` 與少量入口程式需要改 import。

2. **打包與安裝**
   - `pyproject.toml` 的 packages find、package-data key 都要改。
   - 若直接改且無相容層，第三方腳本（`from outlook_mail_extractor import ...`）會立即壞掉。

3. **文件與工具鏈**
   - README、i18n 指令、PowerShell 腳本路徑需同步更新。
   - 變更後需重新檢查 `uv sync`、`uv run mailslide`、測試與 Babel 工作流。

## 風險評估

- **API 破壞風險：高**
  - 任何依賴舊 import path 的內外部腳本都會中斷。
- **回歸風險：中高**
  - 路徑改動量大，容易漏改（測試、腳本、文件、CI）。
- **收益：中低（短期）**
  - 對終端使用者主要價值已由 CLI 名稱 `mailslide` 提供；import path 對一般使用者感知低。

## 建議方案

### 方案 A（推薦）：先維持舊 import path

- 對外維持品牌 `mailslide`（已完成）。
- 內部 package 名保留 `outlook_mail_extractor`。
- 成本最低、風險最低。

### 方案 B：分階段遷移（若你堅持要改）

**Phase 1（相容期，1 個 minor 版本）**
- 新增 `mailslide/` package，對外提供新 import path。
- 保留 `outlook_mail_extractor/` 作為 shim，轉發到 `mailslide`，並記錄 deprecation warning。
- 文件與範例改用 `mailslide`。

**Phase 2（major 版本）**
- 移除 `outlook_mail_extractor` shim。
- Changelog 與 migration guide 明確標示 breaking change。

## 實作工作量估算

- 方案 A：**0.5 天內**（僅文件補註與政策說明）。
- 方案 B：**1.5-3 天**（取決於相容層與回歸測試深度）。

## 驗收清單（若執行方案 B）

- `uv run mailslide --help` 正常。
- 測試全綠（至少 core/i18n/ui schema/CLI smoke）。
- `scripts/i18n.ps1` 與 README 指令路徑一致。
- `from mailslide import ...` 與 `from outlook_mail_extractor import ...`（相容期）皆可用。
- Changelog 有明確遷移說明與移除時程。
