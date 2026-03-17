# /// script
# requires-python = ">=3.13"
# dependencies = [
#    "beautifulsoup4>=4.14.3",
#    "pywin32>=311",
#    "pyyaml>=6.0.3",
# ]
# ///

"""
Outlook Mail Extractor - 讀取 Outlook Classic 指定帳號/目錄郵件 輸出 JSON

此模組提供以下兩種使用方式：

1. 作為 Python 模組匯入使用：
   ```python
   from outlook_mail_extractor import OutlookClient, EmailProcessor

   client = OutlookClient()
   client.connect()
   processor = EmailProcessor(client)
   results = processor.process_job(job_config)
   client.disconnect()
   ```

2. 作為命令列工具使用：
   ```
   python -m outlook_mail_extractor --config config/config.yaml
   ```

   安裝後也可使用：
   ```
   outlook-extract --config config/config.yaml
   ```
"""

# 強制讓 PowerShell 輸出 UTF-8，防止中文亂碼
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 為維持向後相容，原 CLI 入口點直接委派給新模組
from outlook_mail_extractor.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
