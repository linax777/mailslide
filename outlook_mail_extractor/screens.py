"""UI 畫面 - TabbedContent 各標籤頁"""

import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

import pycron
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.timer import Timer
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Log,
    Markdown,
    MarkdownViewer,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.worker import Worker, WorkerState

from outlook_mail_extractor.config import load_config
from outlook_mail_extractor.core import (
    OutlookClient,
    OutlookConnectionError,
    process_config_file,
)
from outlook_mail_extractor.llm import load_llm_config
from outlook_mail_extractor.logger import LoggerManager

from .models import CheckStatus, ConfigStatus, OutlookStatus, SystemStatus

MAX_CELL_LENGTH = 25


def truncate(text: str | None, max_len: int = MAX_CELL_LENGTH) -> str:
    if text is None:
        return ""
    if len(text) > max_len:
        return text[: max_len - 2] + ".."
    return text


CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"
LLM_CONFIG_PATH = Path(__file__).parent.parent / "config" / "llm-config.yaml"
PLUGINS_DIR = Path(__file__).parent.parent / "config" / "plugins"

LEVEL_PRIORITY = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}


class UsageScreen(Static):
    """使用說明分頁"""

    def compose(self) -> ComposeResult:
        content = self._get_usage_content()
        with VerticalScroll():
            yield MarkdownViewer(content)

    def _get_usage_content(self) -> str:
        readme_path = Path(__file__).parent.parent / "README.md"
        if readme_path.exists():
            return readme_path.read_text(encoding="utf-8")
        return "# 使用說明\n\n請參考 README.md"


class AboutScreen(Container):
    """About 標籤頁 - 系統狀態檢查"""

    CONFIG_DIR = Path("config")
    SAMPLE_SUFFIX = ".yaml.sample"
    VERSION = "0.1.0"
    AUTHOR = "linax777"
    REPO_URL = "https://github.com/linax777/outlook-mail-extractor"

    def compose(self) -> ComposeResult:
        yield Static("🔧 系統狀態", id="status-title")
        yield Static("", id="status-content")
        with Horizontal():
            yield Button("初始化設定", id="init-config", variant="primary")
            yield Button("重新檢查", id="refresh-check", variant="default")
        yield Static("", id="about-info")

    def on_mount(self) -> None:
        self._update_init_button()
        self._show_about_info()
        self.run_check()

    def _show_about_info(self) -> None:
        info = f"""📦 版本: {self.VERSION}
👤 作者: {self.AUTHOR}
🔗 GitHub: {self.REPO_URL}
📜 授權: MIT License

一款使用 Python + Textual 開發的 Outlook 郵件提取工具。"""
        self.query_one("#about-info", Static).update(info)

    def _update_init_button(self) -> None:
        all_exist = self._check_all_configs_exist()
        btn = self.query_one("#init-config", Button)
        btn.disabled = all_exist

    def _check_all_configs_exist(self) -> bool:
        if not self.CONFIG_DIR.exists():
            return False
        sample_files = list(self.CONFIG_DIR.rglob(f"*{self.SAMPLE_SUFFIX}"))
        for sample in sample_files:
            yaml_path = sample.with_suffix("")
            if not yaml_path.exists():
                return False
        return True

    def _init_configs(self) -> tuple[int, int]:
        copied = 0
        skipped = 0
        if not self.CONFIG_DIR.exists():
            return (copied, skipped)
        sample_files = list(self.CONFIG_DIR.rglob(f"*{self.SAMPLE_SUFFIX}"))
        for sample in sample_files:
            yaml_path = sample.with_suffix("")
            if yaml_path.exists():
                skipped += 1
            else:
                content = sample.read_text(encoding="utf-8")
                yaml_path.write_text(content, encoding="utf-8")
                copied += 1
        return (copied, skipped)

    def run_check(self) -> None:
        status = self._perform_check()
        self._display_status(status)

    def _perform_check(self) -> SystemStatus:
        config_status = self._check_config()
        outlook_status = self._check_outlook()
        return SystemStatus(config=config_status, outlook=outlook_status)

    def _check_config(self) -> ConfigStatus:
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
        lines = []
        config_icon = "✅" if status.config.status == CheckStatus.OK else "❌"
        outlook_icon = "✅" if status.outlook.status == CheckStatus.OK else "❌"

        lines.append(f"{config_icon} 設定檔: {status.config.message}")
        lines.append(f"{outlook_icon} Outlook: {status.outlook.message}")

        status_content = self.query_one("#status-content", Static)
        status_content.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "init-config":
            copied, skipped = self._init_configs()
            self._update_init_button()
            status_content = self.query_one("#status-content", Static)
            status_content.update(f"已初始化設定檔 (新增: {copied}, 跳過: {skipped})")
            self.run_check()
        elif event.button.id == "refresh-check":
            self.run_check()


class HomeScreen(Static):
    """Home 標籤頁 - 執行 Jobs"""

    def __init__(self):
        super().__init__()
        self._scheduler_enabled = False
        self._cron_expression = "0 * * * *"
        self._last_run_time = None
        self._polling = False

    def compose(self) -> ComposeResult:
        with Vertical(id="home-container"):
            yield Static(
                "⌨️ Tab/方向鍵: 選擇 | Enter: 執行 | 🖱️ 可使用滑鼠操作點擊元件",
                id="help-text",
            )
            with Horizontal(id="home-actions"):
                yield Button("▶️ 執行", id="run-jobs", variant="primary")
                yield Button("🔄 重新整理", id="refresh-jobs")
            yield Static("📋 Jobs 列表", id="jobs-title")
            yield DataTable(id="jobs-table")
            yield Static("📝 執行日誌", id="log-title")
            yield Log(id="log-output", auto_scroll=True)

    def on_mount(self) -> None:
        self._load_jobs()

    def _load_jobs(self) -> None:
        table = self.query_one("#jobs-table", DataTable)

        if not CONFIG_PATH.exists():
            table.add_row("❌ config.yaml 不存在", "", "")
            return

        try:
            config = load_config(CONFIG_PATH)
            table.clear()
            table.add_columns("#", "啟用", "名稱", "帳號", "來源", "目標", "Plugins")

            for idx, job in enumerate(config.get("jobs", []), 1):
                plugins = ", ".join(job.get("plugins", [])) or "-"
                enable = "✓" if job.get("enable", True) else "✗"
                table.add_row(
                    str(idx),
                    enable,
                    truncate(job.get("name", "")),
                    truncate(job.get("account", "")),
                    truncate(job.get("source", "")),
                    truncate(job.get("destination")) or "-",
                    truncate(plugins),
                )
        except Exception as e:
            table.add_row(f"❌ 載入失敗: {e}", "", "")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-jobs":
            self._load_jobs()
        elif event.button.id == "run-jobs":
            self.run_jobs()

    def run_jobs(self) -> None:
        log_widget = self.query_one("#log-output", Log)
        log_widget.clear()

        # 設置 UI sink 回調
        def ui_sink(message: str) -> None:
            self.app.call_from_thread(log_widget.write_line, message)

        LoggerManager.set_ui_sink(ui_sink)
        LoggerManager.start_session(enable_ui_sink=True)

        run_button = self.query_one("#run-jobs", Button)
        run_button.disabled = True

        self.run_worker(self._execute_jobs(), exclusive=True, thread=True)

    async def _execute_jobs(self) -> None:
        try:
            results = await process_config_file(CONFIG_PATH, False)
            self.call_later(self._update_log, "✅ 執行完成")
        except Exception as e:
            import traceback

            error_msg = f"❌ 執行失敗: {e}\n{traceback.format_exc()}"
            self.call_later(self._update_log, error_msg)
        finally:
            LoggerManager.set_ui_sink(None)
            self.call_later(self._enable_button)

    def _update_log(self, text: str) -> None:
        try:
            log = self.query_one("#log-output", Log)
            log.write_line(text)
        except Exception:
            pass

    def _enable_button(self) -> None:
        run_button = self.query_one("#run-jobs", Button)
        run_button.disabled = False


class ScheduleScreen(Static):
    """Schedule 標籤頁 - 排程設定"""

    CSS = """
    #schedule-switch {
        width: 12;
    }
    #cron-input {
        width: 25;
    }
    #schedule-enable-label {
        width: 10;
    }
    #cron-label {
        width: 10;
    }
    """

    def __init__(self):
        super().__init__()
        self._scheduler_enabled = False
        self._cron_expression = "0 * * * *"
        self._last_run_time = None
        self._schedule_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="schedule-container"):
            yield Static(
                "🔄 排程設定，使用時須保持此程式(terminal)運行", id="schedule-title"
            )
            with Vertical(id="schedule-toggle"):
                yield Static("啟用排程:", id="schedule-enable-label")
                yield Switch(id="schedule-switch")
            with Vertical(id="schedule-cron"):
                yield Static("Cron 表達式，點擊下方區域可修改:", id="cron-label")
                yield Input("0 * * * *", id="cron-input", placeholder="* * * * *")
            yield Static("常用範例:", id="examples-title")
            yield Static(
                "0 * * * * - 每小時\n"
                "0 9 * * * - 每天早上 9 點\n"
                "0 9 * * 1-5 - 平日早上 9 點\n"
                "*/15 * * * * - 每 15 分鐘",
                id="examples-content",
            )
            yield Static("📝 排程日誌", id="log-title")
            yield Log(id="log-output", auto_scroll=True)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "schedule-switch":
            if event.switch.value:
                if not self._validate_cron():
                    event.switch.value = False
                    return
            self._scheduler_enabled = event.switch.value
            self._update_schedule_status()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "cron-input":
            self._cron_expression = event.input.value
            self._update_schedule_status()

    def _validate_cron(self) -> bool:
        """驗證 cron 表達式"""
        parts = self._cron_expression.strip().split()
        if len(parts) != 5:
            self._show_error(f"❌ Cron 表達式需有 5 個欄位，實際為 {len(parts)} 個")
            return False

        field_names = ["分鐘", "小時", "日期", "月份", "星期"]
        valid_ranges = [
            (0, 59),  # 分鐘
            (0, 23),  # 小時
            (1, 31),  # 日期
            (1, 12),  # 月份
            (0, 6),  # 星期 (0-6, 0=週日)
        ]

        for i, (part, name, (min_val, max_val)) in enumerate(
            zip(parts, field_names, valid_ranges)
        ):
            if not self._validate_cron_field(part, min_val, max_val):
                self._show_error(f"❌ 第 {i + 1} 個欄位 ({name}) 格式錯誤: {part}")
                return False
        return True

    def _validate_cron_field(self, field: str, min_val: int, max_val: int) -> bool:
        """驗證單個 cron 欄位"""
        if field == "*":
            return True
        if field.startswith("*/"):
            try:
                step = int(field[2:])
                return step > 0
            except ValueError:
                return False
        if "," in field:
            return all(
                self._validate_cron_field(f, min_val, max_val) for f in field.split(",")
            )
        if "-" in field:
            parts = field.split("-")
            if len(parts) != 2:
                return False
            try:
                start, end = int(parts[0]), int(parts[1])
                return min_val <= start <= max_val and min_val <= end <= max_val
            except ValueError:
                return False
        try:
            val = int(field)
            return min_val <= val <= max_val
        except ValueError:
            return False

    def _show_error(self, message: str) -> None:
        """顯示錯誤訊息"""
        self._log(message)
        self.app.notify(message, severity="error")

    def _update_schedule_status(self) -> None:
        if self._scheduler_enabled:
            self._start_scheduler()
        else:
            self._stop_scheduler()

    def _start_scheduler(self) -> None:
        self._last_run_time = datetime.now()
        if self._schedule_timer is not None:
            self._schedule_timer.stop()
        self._schedule_timer = self.set_interval(60, self._check_schedule)
        self._log(f"🔄 排程已啟用: {self._cron_expression}")

    def _stop_scheduler(self) -> None:
        if self._schedule_timer is not None:
            self._schedule_timer.stop()
            self._schedule_timer = None
        self._log("⏹️ 排程已停用")

    def on_unmount(self) -> None:
        self._stop_scheduler()

    def _check_schedule(self) -> None:
        now = datetime.now()
        try:
            if pycron.is_now(self._cron_expression):
                if (
                    self._last_run_time is None
                    or (now - self._last_run_time).total_seconds() > 60
                ):
                    self._last_run_time = now
                    self._log(f"⏰ 排程觸發 ({now.strftime('%H:%M')}): 執行中...")
                    self._run_jobs()
        except Exception as e:
            self._log(f"⚠️ 排程檢查錯誤: {e}")

    def _run_jobs(self) -> None:
        try:
            home_screen = self.app.query_one(HomeScreen)
            home_screen.run_jobs()
        except Exception as e:
            self._log(f"❌ 執行失敗: {e}")

    def _log(self, message: str) -> None:
        try:
            log_widget = self.query_one("#log-output", Log)
            log_widget.write_line(message)
        except Exception:
            pass


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

            table.add_columns(
                "啟用", "名稱", "帳號", "來源", "目標", "Plugins", "Limit"
            )
            for job in config.get("jobs", []):
                plugins = ", ".join(job.get("plugins", [])) or "-"
                enable = "✓" if job.get("enable", True) else "✗"
                table.add_row(
                    enable,
                    truncate(job.get("name", "")),
                    truncate(job.get("account", "")),
                    truncate(job.get("source", "")),
                    truncate(job.get("destination", "")) or "-",
                    truncate(plugins),
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

    CSS = """
    #llm-help {
        width: 100%;
    }
    #llm-examples {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="llm-main"):
            yield Static("🤖 LLM 設定 (config/llm-config.yaml)", id="llm-config-title")
            yield TextArea("", id="llm-config-content", read_only=True)
            yield Static("📊 設定值", id="llm-values-title")
            yield DataTable(id="llm-table")
            yield Static("💡 說明", id="llm-help-title")
            yield Static(
                "• Provider: LLM 供應商 (openai/ollama/llama.cpp 等)\n"
                "• API Base: API 伺服器位址 (如 Ollama 本機: http://localhost:11434/v1)\n"
                "• API Key: API 密鑰 (OpenAI 需要，其他可能可留空)\n"
                "• Model: 模型名稱 (如 llama3, gpt-4 等)\n"
                "• Timeout: 請求逾時秒數",
                id="llm-help",
            )
            yield Static("🔌 連線測試", id="llm-test-title")
            yield Static(
                "點擊「測試連線」按鈕驗證 LLM API 是否可正常連線\n"
                "測試會發送一個簡單的請求確認 API 可用性",
                id="llm-test-desc",
            )
            with Horizontal(id="llm-actions"):
                yield Button("🔗 測試連線", id="test-llm-connection", variant="primary")

    def on_mount(self) -> None:
        self._load_llm_config()

    def _load_llm_config(self) -> None:
        content_widget = self.query_one("#llm-config-content", TextArea)
        table = self.query_one("#llm-table", DataTable)

        try:
            content = LLM_CONFIG_PATH.read_text(encoding="utf-8")
            masked_content = re.sub(r"(api_key:\s*).+", r"\1***", content)
            content_widget.load_text(masked_content)

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
        if not LLM_CONFIG_PATH.exists():
            self.app.notify(
                "❌ llm-config.yaml 不存在，請先建立設定檔",
                severity="error",
            )
            return

        test_button = self.query_one("#test-llm-connection", Button)
        test_button.disabled = True

        self.app.notify("🔄 開始測試 LLM 連線...")

        self.run_worker(self._execute_test(), exclusive=True)

    async def _execute_test(self) -> None:
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
                self.call_later(
                    self.app.notify,
                    "✅ LLM 連線成功！",
                    severity="information",
                )
            else:
                self.call_later(
                    self.app.notify,
                    f"⚠️ LLM 回覆異常: {response[:50]}",
                    severity="warning",
                )
        except Exception as e:
            self.call_later(
                self.app.notify,
                f"❌ LLM 連線失敗: {e}",
                severity="error",
            )
        finally:
            self.call_later(self._enable_button)

    def _enable_button(self) -> None:
        try:
            test_button = self.query_one("#test-llm-connection", Button)
            test_button.disabled = False
        except Exception:
            pass


class PluginsConfigTab(Static):
    """Plugin 設定分頁"""

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-main"):
            yield Static("📦 Plugins", id="plugin-list-title")
            yield DataTable(id="plugin-list", show_cursor=True, cursor_type="row")
            yield Button("🔄 重新整理", id="refresh-plugins", variant="primary")
            yield Static("📄 選取的 Plugin 設定", id="plugin-content-title")
            yield TextArea("", id="plugin-content", read_only=True)

    def on_mount(self) -> None:
        self._load_plugins()

    def on_show(self) -> None:
        self._load_plugins()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-plugins":
            self._load_plugins()

    def _load_plugins(self) -> None:
        title = self.query_one("#plugin-list-title", Static)
        table = self.query_one("#plugin-list", DataTable)

        table.clear()
        table.add_columns("Plugin 名稱", "狀態")

        if not PLUGINS_DIR.exists():
            title.update("📦 Plugins (目錄不存在)")
            table.add_row("❌ plugins 目錄不存在", "")
            return

        plugin_files = sorted(PLUGINS_DIR.glob("*.yaml*"))

        if not plugin_files:
            title.update("📦 Plugins (0 個)")
            table.add_row("(無 Plugin 設定檔)", "")
            return

        seen: set[str] = set()
        for pf in plugin_files:
            if pf.name.endswith(".yaml.sample"):
                name = pf.name[:-12]
                is_sample = True
            else:
                name = pf.stem
                is_sample = False
            if name in seen:
                continue
            seen.add(name)
            status = "sample" if is_sample else "active"
            table.add_row(name, status)

        title.update(f"📦 Plugins ({len(seen)} 個)")

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
