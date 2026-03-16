
# 📅 Outlook AI 行事曆自動化開發計畫

## 一、 系統架構設計 (Modular Architecture)

為了便於日後打磨 Parser 並確保系統穩定，建議將專案拆分為以下四大模組：
- Email Parser (核心邏輯層)：純 Python 邏輯，負責處理如 V{eu FocusedInbox 等二進位雜訊、過濾長串追蹤網址、提取 HTML 表格。
- Outlook Client (硬體操作層)：封裝 pywin32，負責從本地 Outlook 讀取郵件、移動目錄、寫入行事曆。
- lamacpp + 本地模型 (AI推論) : 分析郵件 json，提取可能的會議/講座/課程通知，轉出 json 格式讓 outlook client 寫入行事曆

## 二、 開發階段與里程碑

### 第一階段

- 核心 Parser 打磨與離線測試針對您上傳的雜訊郵件（例如微軟講座邀請 ），建立穩定的清洗邏輯：雜訊清理 (Sanitization)：使用 Regex 剔除長度超過 25 字元的隨機編碼與 Base64 雜訊 。
- 結構化優化：優先保護郵件主旨（如「微軟最新生產力線上講座」），並將追蹤連結（如 safelinks.protection.outlook.com ）替換為簡約占位符。離線測試環境：將 .msg 的 Body 提取存成 .txt 進行單元測試，不再依賴 Outlook 執行環境。

### 第二階段

- 郵件爬取與 llama.cpp server 推送 (Job Runner)YAML 配置管理：支援多帳號、來源目錄（如「收件匣」）與目的目錄（如「AI_Processed」）的設定。
- 批次處理流程：Python 爬取指定目錄 -> Parser 清理 -> 封裝為 JSON -> POST 推送到本地 llama.cpp  llama-server。
- 狀態轉移：成功推送後，利用 msg.Move() 將郵件移走，確保流程不重複。

### 第三階段

- llama.cpp  llama-server  提取會議/講座/課程通知 start_time、duration 與 location。


### 第四階段

- Outlook worker 將接收到的 JSON 解析為 CalendarEvent 物件。
- Outlook 寫入：調用 appt.Save() 將活動寫入本地 Outlook Classic 行事曆。

## GUI 介面

- 使用 flet 打造 GUI 介面，目標是成為 可在 windows 背景執行的工具程式
- GUI 可設定 yaml config 並驗證後儲存
- 有按鈕可手動執行 mail parser 並導出 json
- 可設定排程定期執行 mail parser
- 開啟 SERVER MODE 之後，parser 會自動將 json POST 到 llama.cpp  llama-server
- 開啟 SERVER MODE 之後，有 FASTAPI 介面可以接收 llama-cpp 的 json，並轉換為 outlook calendar event


## 實行推薦方案：安裝程式 + 模型分離

### 做法：

1. __PyInstaller__ 打包 Python + GUI + llama.cpp 為單一 exe（約 150-200MB）

2. __Inno Setup / NSIS__ 製作安裝程式

3. 安裝時提供兩個選項：

   - __精簡版__：只安裝 exe，讓使用者自己下載模型
   - __完整版__：包含模型檔（但安裝包會是 4GB+）

### 更聰明的做法：模型隨選下載

- 安裝程式只包 exe（約 150MB）
- 首次啟動時，程式自動偵測模型是否存在
- 若不存在，顯示簡單的「下載模型」按鈕
- 從 GitHub Release 或雲端下載模型到本機

---

## 📋 實作步驟

1. __完善 PyInstaller 設定__ - 加入 llama.cpp binding
2. __建立模型下載機制__ - 首次執行時檢查並下載
3. __製作安裝程式__ - Inno Setup 腳本
4. __發布到 GitHub Release__ - exe + 模型分開提供

---

## 💡 額外建議：考慮模型大小

你的 `Qwen3.5-4B-UD-Q4_K_XL.gguf` 是 4GB+，其實可以考慮：

- __Qwen2.5-1.5B__ 或 __Phi-3-mini__（約 2-4GB）
- 犧牲一些準確率，但大幅減少分發成本
- 或者維持 4GB，說明這是「完整版」的需求


## python 代碼 啟動 llama-server + API

```python
import subprocess
import requests
import time
import os
import sys

# 取得 exe 同目錄
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

class LlamaServer:
    def __init__(self, model_path: str, port: int = 8080):
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.process = None
        self.model_path = os.path.join(BASE_DIR, model_path)
        
    def start(self):
        server_path = os.path.join(BASE_DIR, "llama-server.exe")
        self.process = subprocess.Popen(
            [server_path, "-m", self.model_path, "-c", "2048", "-p", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        # 等待啟動
        for _ in range(30):
            try:
                requests.get(f"{self.base_url}/health", timeout=1)
                return
            except:
                time.sleep(0.5)
        raise RuntimeError("llama-server 啟動失敗")
    
    def stop(self):
        if self.process:
            self.process.terminate()
    
    def chat(self, prompt: str) -> str:
        resp = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json={
                "model": "model",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        return resp.json()["choices"][0]["message"]["content"]
```

## llama-server 分析

```python
import requests

# 一次請求分析單封郵件
def analyze_email(content: str):
    resp = requests.post(
        "http://localhost:8080/v1/chat/completions",
        json={
            "model": "model",
            "messages": [
                {"role": "system", "content": "你是一個郵件分析助手..."},
                {"role": "user", "content": f"分析這封郵件：{content}"}
            ]
        },
        timeout=30
    )
    return resp.json()["choices"][0]["message"]["content"]
```

## TUI 設計 (Textual)