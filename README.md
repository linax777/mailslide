# Outlook Mail Extractor

提取郵件內文工具

## 快速開始

```bash
# 安裝依賴
uv pip install -e .

# 執行應用程式
uv run python app.py
```

## 專案架構

```text
outlook_mail_extractor/
├── app.py              # 應用程式入口 (Textual App)
├── config.yaml         # 執行期設定檔
├── config.yaml.sample # 設定檔範本
│
└── outlook_mail_extractor/
    ├── __init__.py
    ├── config.py      # 設定檔載入與驗證
    ├── core.py        # Outlook COM 連線與郵件處理
    ├── parser.py      # 郵件內容解析
    ├── models.py      # 資料模型 (MVC - Model)
    └── screens.py     # UI 畫面 (MVC - View/Controller)
```

## 開發指南

### 執行方式

```bash
uv run python app.py
```

### 新增功能

#### 1. 新增標籤頁 (Tab)

在 `screens.py` 中新增一個繼承自 `Static` 的類別，然後在 `app.py` 的 `compose()` 中加入 `TabPane`。

#### 2. 新增資料模型

在 `models.py` 中使用 `dataclass` 定義資料結構。

#### 3. 新增檢查項目 (在 Home 標籤頁)

修改 `screens.py` 中的 `HomeScreen` 類別：

- 在 `_perform_check()` 中加入新的檢查方法
- 在 `SystemStatus` dataclass 中加入新欄位
- 更新 `_display_status()` 顯示結果

### 按鍵快捷鍵

| 按鍵 | 功能 |
|------|------|
| `d` | 切換深色/淺色模式 |
| `Ctrl+p` | 開啟命令面板 |

### 設定檔格式

```yaml
jobs:
  - name: "任務名稱"
    account: "your@email.com"
    source: "收件匣"
    destination: "已處理"
    limit: 5
```

## 技術棧

- **Textual** - TUI 框架
- **python-win32com** - Outlook COM 連線
- **PyYAML** - 設定檔解析

## 注意事項

- 僅支援 Windows + Outlook Classic (非 New Outlook)
- 執行時需開啟 Outlook 應用程式
- 設定檔需命名為 `config.yaml`
