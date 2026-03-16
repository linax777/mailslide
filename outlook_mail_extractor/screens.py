"""UI 畫面 - TabbedContent 各標籤頁"""

from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import Button, Static

from outlook_mail_extractor.config import load_config
from outlook_mail_extractor.core import OutlookClient, OutlookConnectionError

from .models import CheckStatus, ConfigStatus, OutlookStatus, SystemStatus


class HomeScreen(Static):
    """Home 標籤頁 - 系統狀態檢查"""

    def compose(self) -> ComposeResult:
        yield Static("系統狀態檢查", id="status-title")
        yield Static("", id="status-content")
        yield Button("重新檢查", id="refresh-check", variant="primary")

    def on_mount(self) -> None:
        self.run_check()

    def run_check(self) -> None:
        """執行系統檢查"""
        status = self._perform_check()
        self._display_status(status)

    def _perform_check(self) -> SystemStatus:
        """執行各項檢查"""
        # 檢查設定檔
        config_status = self._check_config()

        # 檢查 Outlook 連線
        outlook_status = self._check_outlook()

        return SystemStatus(config=config_status, outlook=outlook_status)

    def _check_config(self) -> ConfigStatus:
        """檢查設定檔"""
        config_path = Path("config.yaml")
        if not config_path.exists():
            return ConfigStatus(
                status=CheckStatus.ERROR,
                message="找不到 config.yaml，請參考 config.yaml.sample 建立",
            )

        try:
            load_config(config_path)
            return ConfigStatus(status=CheckStatus.OK, message="正常")
        except Exception as e:
            return ConfigStatus(status=CheckStatus.ERROR, message=f"格式錯誤 - {e}")

    def _check_outlook(self) -> OutlookStatus:
        """檢查 Outlook 連線"""
        try:
            client = OutlookClient()
            client.connect()
            accounts = client.list_accounts()
            client.disconnect()
            return OutlookStatus(
                status=CheckStatus.OK,
                message=f"已連線 ({len(accounts)} 個帳號)",
                account_count=len(accounts),
            )
        except OutlookConnectionError as e:
            return OutlookStatus(status=CheckStatus.ERROR, message=str(e))
        except Exception as e:
            return OutlookStatus(status=CheckStatus.ERROR, message=f"連線失敗 - {e}")

    def _display_status(self, status: SystemStatus) -> None:
        """顯示狀態結果"""
        lines = []
        config_icon = "✅" if status.config.status == CheckStatus.OK else "❌"
        outlook_icon = "✅" if status.outlook.status == CheckStatus.OK else "❌"

        lines.append(f"{config_icon} 設定檔: {status.config.message}")
        lines.append(f"{outlook_icon} Outlook: {status.outlook.message}")

        status_content = self.query_one("#status-content", Static)
        status_content.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """處理按鈕點擊事件"""
        if event.button.id == "refresh-check":
            self.run_check()


class ConfigScreen(Static):
    """Configuration 標籤頁 - 設定檔資訊"""

    def compose(self) -> ComposeResult:
        yield Static("設定檔路徑: config.yaml")
