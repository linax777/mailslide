"""Outlook 連線與郵件處理核心模組"""

from pathlib import Path

import pythoncom
import win32com.client

from .parser import clean_content, clean_invisible_chars, parse_tables


class OutlookConnectionError(Exception):
    """無法連線至 Outlook 時拋出"""

    pass


class FolderNotFoundError(Exception):
    """找不到指定資料夾時拋出"""

    pass


class OutlookClient:
    """Outlook COM 連線管理"""

    def __init__(self):
        self._outlook = None
        self._mapi = None
        self._connected = False

    def connect(self) -> None:
        """
        建立 Outlook 連線

        Raises:
            OutlookConnectionError: 無法連線時
        """
        try:
            pythoncom.CoInitialize()
            self._outlook = win32com.client.Dispatch("Outlook.Application")
            self._mapi = self._outlook.GetNamespace("MAPI")
            self._connected = True
        except Exception as e:
            pythoncom.CoUninitialize()
            raise OutlookConnectionError(
                f"無法連線至 Outlook。請確認已安裝並登入 Microsoft Outlook Classic。\n"
                f"詳細錯誤: {e}"
            ) from e

    def disconnect(self) -> None:
        """關閉 Outlook 連線"""
        if self._connected:
            pythoncom.CoUninitialize()
            self._outlook = None
            self._mapi = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """檢查是否已連線"""
        return self._connected

    def list_accounts(self) -> list[str]:
        """
        列出所有可用帳號

        Returns:
            帳號名稱列表
        """
        if not self._connected:
            raise OutlookConnectionError("尚未連線，請先呼叫 connect()")
        return [store.Name for store in self._mapi.Folders]

    def get_folder(
        self, account: str, folder_path: str, create_if_missing: bool = False
    ):
        """
        取得指定帳號下的資料夾

        Args:
            account: 帳號名稱
            folder_path: 資料夾路徑 (如 "Inbox/Archive" 或 "Inbox\\Archive")
            create_if_missing: 是否在不存在時建立

        Returns:
            Folder 物件

        Raises:
            FolderNotFoundError: 找不到資料夾時
        """
        if not self._connected:
            raise OutlookConnectionError("尚未連線，請先呼叫 connect()")

        try:
            acc_root = self._mapi.Folders[account]
        except Exception as e:
            raise FolderNotFoundError(f"找不到帳號: {account}") from e

        current_folder = acc_root
        parts = folder_path.replace("\\", "/").split("/")
        for part in parts:
            if not part:
                continue
            try:
                current_folder = current_folder.Folders[part]
            except Exception:
                if create_if_missing:
                    current_folder.Folders.Add(part)
                    current_folder = current_folder.Folders[part]
                else:
                    raise FolderNotFoundError(f"找不到路徑: {part}")
        return current_folder


class EmailProcessor:
    """郵件處理邏輯"""

    def __init__(self, client: OutlookClient):
        """
        初始化郵件處理器

        Args:
            client: 已連線的 OutlookClient 實例
        """
        self._client = client

    def extract_email_data(self, message) -> dict:
        """
        擷取單封郵件的資料

        Args:
            message: Outlook MailItem 物件

        Returns:
            包含郵件資料的字典
        """
        raw_body = str(message.Body) if getattr(message, "Body", None) else ""
        clean_body = clean_content(raw_body)

        return {
            "subject": message.Subject,
            "sender": (
                message.SenderEmailAddress
                if hasattr(message, "SenderEmailAddress")
                else message.SenderName
            ),
            "received": str(message.ReceivedTime),
            "body": clean_body,
            "tables": parse_tables(message.HTMLBody),
        }

    def process_job(
        self,
        job_config: dict,
        dry_run: bool = False,
        move_on_process: bool = True,
    ) -> list[dict]:
        """
        處理單個 job 設定

        Args:
            job_config: 包含 name, account, source, destination, limit 的字典
            dry_run: 是否為測試模式 (不實際移動郵件)
            move_on_process: 是否在處理後移動郵件

        Returns:
            處理結果列表
        """
        job_name = job_config.get("name", "Unnamed Job")
        account_name = job_config.get("account")
        source_path = job_config["source"]
        dest_path = job_config.get("destination")
        limit = job_config.get("limit", 5)

        # 取得來源資料夾
        src_folder = self._client.get_folder(account_name, source_path)

        # 取得目的資料夾
        dest_folder = None
        if dest_path:
            dest_folder = self._client.get_folder(
                account_name, dest_path, create_if_missing=not dry_run
            )

        # 取得郵件
        messages = src_folder.Items
        messages.Sort("[ReceivedTime]", True)  # 由新到舊

        # 收集要處理的郵件
        items_to_process = []
        item = messages.GetFirst()
        count = 0

        while item:
            if count >= limit:
                break
            if item.Class == 43:  # olMail
                items_to_process.append(item)
                count += 1
            item = messages.GetNext()

        # 處理郵件
        job_emails = []
        for msg in items_to_process:
            email_data = self.extract_email_data(msg)
            job_emails.append(email_data)

            # 移動郵件
            if move_on_process and not dry_run and dest_folder:
                msg.Move(dest_folder)

        return job_emails


def process_config_file(
    config_file: Path | str,
    dry_run: bool = False,
    move_on_process: bool = True,
) -> dict:
    """
    便利函式：直接處理設定檔

    Args:
        config_file: YAML 設定檔路徑
        dry_run: 測試模式
        move_on_process: 是否在處理後移動郵件

    Returns:
        所有 job 的處理結果
    """
    from .config import load_config

    config = load_config(config_file)
    client = OutlookClient()
    client.connect()

    try:
        processor = EmailProcessor(client)
        all_results = {}

        for job in config.get("jobs", []):
            job_name = job.get("name", "Unnamed Job")
            results = processor.process_job(job, dry_run, move_on_process)
            all_results[job_name] = results

        # 清理不可見字元
        return clean_invisible_chars(all_results)
    finally:
        client.disconnect()
