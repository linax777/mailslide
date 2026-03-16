"""UI 畫面 - TabbedContent 各標籤頁"""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Static, TabbedContent, TabPane, TextArea

from outlook_mail_extractor.config import load_config
from outlook_mail_extractor.core import OutlookClient, OutlookConnectionError
from outlook_mail_extractor.llm import load_llm_config

from .models import CheckStatus, ConfigStatus, OutlookStatus, SystemStatus

CONFIG_PATH = Path("config/config.yaml")
LLM_CONFIG_PATH = Path("config/llm-config.yaml")
PLUGINS_DIR = Path("config/plugins")


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
        config_status = self._check_config()
        outlook_status = self._check_outlook()
        return SystemStatus(config=config_status, outlook=outlook_status)

    def _check_config(self) -> ConfigStatus:
        """檢查設定檔"""
        config_path = CONFIG_PATH
        if not config_path.exists():
            return ConfigStatus(
                status=CheckStatus.ERROR,
                message="找不到 config.yaml，請參考 config/config.yaml.sample 建立",
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


class MainConfigTab(Static):
    """一般設定分頁"""

    def compose(self) -> ComposeResult:
        yield Static("📄 主設定檔 (config/config.yaml)", id="main-config-title")
        yield TextArea("", id="main-config-content", read_only=True)
        yield Static("📋 Jobs 列表", id="jobs-title")
        yield DataTable(id="jobs-table")

    def on_mount(self) -> None:
        self._load_config()

    def _load_config(self) -> None:
        content_widget = self.query_one("#main-config-content", TextArea)
        table = self.query_one("#jobs-table", DataTable)

        if not CONFIG_PATH.exists():
            content_widget.load_text("❌ 檔案不存在")
            return

        try:
            content = CONFIG_PATH.read_text(encoding="utf-8")
            content_widget.load_text(content)

            config = load_config(CONFIG_PATH)
            table.clear()

            table.add_columns("名稱", "帳號", "來源資料夾", "目標資料夾", "Limit")
            for job in config.get("jobs", []):
                table.add_row(
                    job.get("name", ""),
                    job.get("account", ""),
                    job.get("source", ""),
                    job.get("destination", ""),
                    str(job.get("limit", "")),
                )

            status = Static("✅ 設定檔格式正確", id="main-config-status")
            self.query_one("#main-config-title", Static).update(
                "📄 主設定檔 (config/config.yaml) ✅"
            )
        except Exception as e:
            self.query_one("#main-config-title", Static).update(
                f"📄 主設定檔 (config/config.yaml) ❌ {e}"
            )


class LLMConfigTab(Static):
    """LLM 設定分頁"""

    def compose(self) -> ComposeResult:
        yield Static("🤖 LLM 設定 (config/llm-config.yaml)", id="llm-config-title")
        yield TextArea("", id="llm-config-content", read_only=True)
        yield Static("📊 設定值", id="llm-values-title")
        yield DataTable(id="llm-table")
        with Horizontal(id="llm-actions"):
            yield Button("🔗 測試連線", id="test-llm-connection", variant="primary")
            yield Static("", id="llm-test-result")

    def on_mount(self) -> None:
        self._load_llm_config()

    def _load_llm_config(self) -> None:
        content_widget = self.query_one("#llm-config-content", TextArea)
        table = self.query_one("#llm-table", DataTable)

        if not LLM_CONFIG_PATH.exists():
            content_widget.load_text("❌ 檔案不存在 (將使用預設值)")
            return

        try:
            content = LLM_CONFIG_PATH.read_text(encoding="utf-8")
            content_widget.load_text(content)

            llm_config = load_llm_config()
            table.clear()
            table.add_columns("項目", "值")
            table.add_row("Provider", llm_config.provider)
            table.add_row("API Base", llm_config.api_base)
            table.add_row("API Key", "***" if llm_config.api_key else "(未設定)")
            table.add_row("Model", llm_config.model)
            table.add_row("Timeout", f"{llm_config.timeout} 秒")

            self.query_one("#llm-config-title", Static).update(
                "🤖 LLM 設定 (config/llm-config.yaml) ✅"
            )
        except Exception as e:
            self.query_one("#llm-config-title", Static).update(
                f"🤖 LLM 設定 (config/llm-config.yaml) ❌ {e}"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "test-llm-connection":
            self._test_llm_connection()

    def _test_llm_connection(self) -> None:
        result_widget = self.query_one("#llm-test-result", Static)
        result_widget.update("🔄 測試中...")

        try:
            llm_config = load_llm_config()
            from outlook_mail_extractor.llm import LLMClient

            client = LLMClient(llm_config)
            response = client.chat(
                system_prompt="只用一個詞回覆：OK",
                user_prompt="Hi",
                temperature=0,
            )
            client.close()

            if "ok" in response.lower():
                result_widget.update("✅ 連線成功！")
            else:
                result_widget.update(f"⚠️ 回覆異常: {response[:50]}")
        except Exception as e:
            result_widget.update(f"❌ 連線失敗: {e}")


class PluginsConfigTab(Static):
    """Plugin 設定分頁"""

    def compose(self) -> ComposeResult:
        with Horizontal(id="plugin-list-container"):
            yield Static("📦 Plugins", id="plugin-list-title")
            yield DataTable(id="plugin-list")
        yield Static("📄 選取的 Plugin 設定", id="plugin-content-title")
        yield TextArea("", id="plugin-content", read_only=True)

    def on_mount(self) -> None:
        self._load_plugins()

    def _load_plugins(self) -> None:
        table = self.query_one("#plugin-list", DataTable)

        if not PLUGINS_DIR.exists():
            table.add_row("❌ plugins 目錄不存在")
            return

        table.clear()
        table.add_columns("Plugin 名稱", "狀態")

        plugin_files = sorted(PLUGINS_DIR.glob("*.yaml"))
        if not plugin_files:
            table.add_row("(無 Plugin 設定檔)", "")
        else:
            for pf in plugin_files:
                name = pf.stem
                is_sample = pf.suffix == ".yaml.sample"
                status = "📝 sample" if is_sample else "✅ 已啟用"
                table.add_row(name, status)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#plugin-list", DataTable)
        row = table.get_row_at(event.cursor_row)
        if row:
            plugin_name = row[0]
            self._load_plugin_content(plugin_name)

    def _load_plugin_content(self, plugin_name: str) -> None:
        content_widget = self.query_one("#plugin-content", TextArea)

        sample_path = PLUGINS_DIR / f"{plugin_name}.yaml.sample"
        normal_path = PLUGINS_DIR / f"{plugin_name}.yaml"

        file_path = normal_path if normal_path.exists() else sample_path

        if not file_path.exists():
            content_widget.load_text("❌ 檔案不存在")
            return

        try:
            content = file_path.read_text(encoding="utf-8")
            content_widget.load_text(content)
            self.query_one("#plugin-content-title", Static).update(
                f"📄 {plugin_name} 設定 ✅"
            )
        except Exception as e:
            content_widget.load_text(f"❌ 讀取失敗: {e}")
            self.query_one("#plugin-content-title", Static).update(
                f"📄 {plugin_name} 設定 ❌"
            )


class ConfigScreen(Static):
    """Configuration 標籤頁 - 設定檔檢視"""

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="main"):
            with TabPane("一般設定", id="main"):
                yield MainConfigTab()
            with TabPane("LLM 設定", id="llm"):
                yield LLMConfigTab()
            with TabPane("Plugin 設定", id="plugins"):
                yield PluginsConfigTab()
