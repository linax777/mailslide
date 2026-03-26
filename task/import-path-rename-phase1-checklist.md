# Import Path Rename - Phase 1 相容層實作清單

目標：在不破壞既有使用者的前提下，新增 `mailslide` import path，並保留 `outlook_mail_extractor` 相容。

## 1) 新增 `mailslide` 相容 package

- [ ] 建立目錄 `mailslide/`
- [ ] 新增 `mailslide/__init__.py`
  - 匯出與 `outlook_mail_extractor.__init__` 相同的 public API（`__all__` 與 `__version__`）
  - 由 `outlook_mail_extractor` 轉發（import + re-export）
- [ ] 新增 `mailslide/__main__.py`
  - 轉發到 `outlook_mail_extractor.__main__.main`

## 2) 保留舊路徑並加入 deprecation 提示（可選）

- [ ] 在 `outlook_mail_extractor/__init__.py` 增加一次性 warning（可用環境變數關閉）
  - 訊息：建議逐步改用 `mailslide` import path
  - 注意：避免每次 import 都噴訊息（只提示一次）

## 3) 更新打包設定（同時支援雙路徑）

- [ ] `pyproject.toml`
  - `tool.setuptools.packages.find.include` 改為同時包含：
    - `outlook_mail_extractor*`
    - `mailslide*`
  - `tool.setuptools.package-data` 保持掛在實際資源所在 package（目前是 `outlook_mail_extractor`）
  - `project.scripts` 維持 `mailslide`（不新增舊 CLI）

## 4) 文件與範例

- [ ] `README.md` / `README.en.md`
  - 新增一小段「Python import 遷移」
  - 範例改為 `from mailslide import ...`
  - 說明相容期仍支援 `outlook_mail_extractor`

## 5) 測試補強

- [ ] 新增 `tests/test_import_compat.py`
  - 驗證 `import mailslide` 可用
  - 驗證 `from mailslide import __version__` 與舊路徑一致
  - 驗證舊路徑仍可 import（相容期）
- [ ] 既有測試可先不全量改 import，確保相容

## 6) 驗收命令

- [ ] `uv sync`
- [ ] `uv run python -c "import mailslide; print(mailslide.__version__)"`
- [ ] `uv run python -c "import outlook_mail_extractor as o; print(o.__version__)"`
- [ ] `uv run mailslide --help`
- [ ] `uv run pytest -q tests/test_import_compat.py tests/test_i18n.py`

## 7) 後續移除時程（Phase 2 / major）

- [ ] 在 Changelog 註記：下一個 major 版移除 `outlook_mail_extractor` 相容層
- [ ] major 版時移除 shim 與 deprecation 豁免
