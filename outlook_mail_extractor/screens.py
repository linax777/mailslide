"""UI 畫面 - TabbedContent 各標籤頁"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pycron
import yaml
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Log,
    MarkdownViewer,
    SelectionList,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.worker import Worker

from outlook_mail_extractor.config import load_config
from outlook_mail_extractor.core import OutlookConnectionError
from outlook_mail_extractor.llm import load_llm_config
from outlook_mail_extractor.runtime import RuntimeContext, get_runtime_context
from outlook_mail_extractor.services.job_execution import JobExecutionService
from outlook_mail_extractor.services.preflight import PreflightCheckService
from outlook_mail_extractor.ui_schema import (
    build_default_list_item,
    evaluate_rules,
    load_plugin_ui_schema,
    load_ui_schema,
    strip_reserved_metadata,
    validate_ui_schema,
)

from .models import CheckStatus, ConfigStatus, OutlookStatus, SystemStatus

MAX_CELL_LENGTH = 25


def truncate(text: str | None, max_len: int = MAX_CELL_LENGTH) -> str:
    if text is None:
        return ""
    if len(text) > max_len:
        return text[: max_len - 2] + ".."
    return text


LEVEL_PRIORITY = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}


class UsageScreen(Static):
    """使用說明分頁"""

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()

    def compose(self) -> ComposeResult:
        content = self._get_usage_content()
        with VerticalScroll():
            yield MarkdownViewer(content)

    def _get_usage_content(self) -> str:
        readme_path = self._runtime.paths.readme_file
        if readme_path.exists():
            return readme_path.read_text(encoding="utf-8")
        return "# 使用說明\n\n請參考 README.md"


class AboutScreen(Container):
    """About 標籤頁 - 系統狀態檢查"""

    SAMPLE_SUFFIX = ".yaml.sample"
    VERSION = "0.2"
    AUTHOR = "linax777"
    REPO_URL = "https://github.com/linax777/outlook-mail-extractor"

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()

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
        config_dir = self._runtime.paths.config_dir
        if not config_dir.exists():
            return False
        sample_files = list(config_dir.rglob(f"*{self.SAMPLE_SUFFIX}"))
        for sample in sample_files:
            yaml_path = sample.with_suffix("")
            if not yaml_path.exists():
                return False
        return True

    def _init_configs(self) -> tuple[int, int]:
        copied = 0
        skipped = 0
        config_dir = self._runtime.paths.config_dir
        if not config_dir.exists():
            return (copied, skipped)
        sample_files = list(config_dir.rglob(f"*{self.SAMPLE_SUFFIX}"))
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
        config_path = self._runtime.paths.config_file
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
            config_path = self._runtime.paths.config_file
            config = load_config(config_path) if config_path.exists() else None
            preflight = PreflightCheckService(
                client_factory=self._runtime.client_factory,
            )
            result = preflight.run(config) if config else preflight.run({"jobs": []})

            if result.issues:
                issue_preview = "；".join(result.issues[:2])
                if len(result.issues) > 2:
                    issue_preview += f"；另有 {len(result.issues) - 2} 個 jobs 設定有誤"
                return OutlookStatus(
                    status=CheckStatus.ERROR,
                    message=f"設定檢查失敗 - {issue_preview}",
                    account_count=result.account_count,
                )

            return OutlookStatus(
                status=CheckStatus.OK,
                message=f"已連線 ({result.account_count} 個帳號)",
                account_count=result.account_count,
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

    CSS = """
    #home-actions {
        height: auto;
    }
    #toggle-preserve-reply-thread {
        margin: 0 0 0 2;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        self._scheduler_enabled = False
        self._cron_expression = "0 * * * *"
        self._last_run_time = None
        self._polling = False
        self._preserve_reply_thread = True
        self._job_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="home-container"):
            yield Static(
                "⌨️ Tab/方向鍵: 選擇 | Enter: 執行 | 🖱️ 可使用滑鼠操作點擊元件",
                id="help-text",
            )
            yield Static("", id="home-status")
            with Horizontal(id="home-actions"):
                yield Button("▶️ 執行", id="run-jobs", variant="primary")
                yield Button("⏹️ 終止", id="stop-jobs", variant="error", disabled=True)
                yield Button("🔄 重新整理", id="refresh-jobs")
                yield Button(
                    "保留 RE/FW: ON",
                    id="toggle-preserve-reply-thread",
                    variant="default",
                )
            yield Static("📋 Jobs 列表", id="jobs-title")
            yield DataTable(id="jobs-table")
            yield Static("📝 執行日誌", id="log-title")
            yield Log(id="log-output", auto_scroll=True)

    def on_mount(self) -> None:
        self._update_preserve_reply_button()
        self._load_jobs()

    def _load_jobs(self) -> None:
        table = self.query_one("#jobs-table", DataTable)
        status = self.query_one("#home-status", Static)
        run_button = self.query_one("#run-jobs", Button)
        table.clear(columns=True)

        config_path = self._runtime.paths.config_file
        if not config_path.exists():
            status.update("⚠️ 尚未初始化設定，請到 About 分頁按「初始化設定」。")
            table.add_columns("狀態", "說明")
            table.add_row("未初始化", "找不到 config/config.yaml")
            run_button.disabled = True
            return

        try:
            config = load_config(config_path)
            status.update("")
            table.add_columns("#", "啟用", "名稱", "帳號", "來源", "目標", "Plugins")
            run_button.disabled = False

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
            status.update("⚠️ 設定檔存在，但格式異常，請先修正後再執行。")
            table.add_columns("狀態", "說明")
            table.add_row("載入失敗", str(e))
            run_button.disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-jobs":
            self._load_jobs()
        elif event.button.id == "run-jobs":
            self.run_jobs()
        elif event.button.id == "stop-jobs":
            self.stop_jobs()
        elif event.button.id == "toggle-preserve-reply-thread":
            self._preserve_reply_thread = not self._preserve_reply_thread
            self._update_preserve_reply_button()
            status = "啟用" if self._preserve_reply_thread else "停用"
            self.app.notify(f"RE/FW 內文保留：{status}", severity="information")

    def _update_preserve_reply_button(self) -> None:
        """Update preserve-reply-thread toggle button label."""
        button = self.query_one("#toggle-preserve-reply-thread", Button)
        button.label = (
            "保留 RE/FW: ON" if self._preserve_reply_thread else "保留 RE/FW: OFF"
        )

    def run_jobs(self) -> None:
        if self._job_worker and self._job_worker.is_running:
            self.app.notify("⚠️ 作業正在執行中", severity="warning")
            return

        if not self._validate_jobs_before_run():
            return

        log_widget = self.query_one("#log-output", Log)
        log_widget.clear()

        # 設置 UI sink 回調
        def ui_sink(message: str) -> None:
            self.app.call_from_thread(log_widget.write_line, message)

        self._runtime.logger_manager.set_ui_sink(ui_sink)
        self._runtime.logger_manager.start_session(enable_ui_sink=True)

        self._set_job_running_state(True)
        self._job_worker = self.run_worker(
            self._execute_jobs(),
            exclusive=True,
            thread=True,
        )

    def stop_jobs(self) -> None:
        """Request cancellation for the current job worker."""
        if not self._job_worker or not self._job_worker.is_running:
            self.app.notify("ℹ️ 目前沒有執行中的作業", severity="information")
            self._set_job_running_state(False)
            return

        self._job_worker.cancel()
        self._update_log("⏹️ 已送出終止要求，正在停止作業...")
        self.app.notify("⏹️ 已送出終止要求", severity="warning")

        # Keep stop disabled while waiting for worker teardown.
        stop_button = self.query_one("#stop-jobs", Button)
        stop_button.disabled = True

    def _validate_jobs_before_run(self) -> bool:
        """Validate enabled jobs before starting execution."""
        try:
            config = load_config(self._runtime.paths.config_file)
        except Exception as e:
            self.app.notify(f"❌ 無法載入設定檔: {e}", severity="error")
            return False

        enabled_jobs = [
            job for job in config.get("jobs", []) if job.get("enable", True)
        ]
        if not enabled_jobs:
            self.app.notify("⚠️ 沒有可執行的啟用 jobs", severity="warning")
            return False

        try:
            preflight = PreflightCheckService(
                client_factory=self._runtime.client_factory,
            )
            result = preflight.run(
                {"jobs": enabled_jobs},
            )
        except OutlookConnectionError as e:
            self.app.notify(f"❌ Outlook 連線失敗: {e}", severity="error")
            return False
        except Exception as e:
            self.app.notify(f"❌ 執行前檢查失敗: {e}", severity="error")
            return False

        if result.issues:
            for issue in result.issues[:3]:
                self.app.notify(f"⚠️ {issue}", severity="error")
            if len(result.issues) > 3:
                self.app.notify(
                    f"⚠️ 另有 {len(result.issues) - 3} 個 job 的 account/source 設定有誤",
                    severity="error",
                )
            return False

        return True

    async def _execute_jobs(self) -> None:
        try:
            execution_service = JobExecutionService(
                client_factory=self._runtime.client_factory,
                logger_manager=self._runtime.logger_manager,
                default_llm_config_path=self._runtime.paths.llm_config_file,
                default_plugin_config_dir=self._runtime.paths.plugins_dir,
            )
            await execution_service.process_config_file(
                self._runtime.paths.config_file,
                False,
                preserve_reply_thread=self._preserve_reply_thread,
            )
            self.call_later(self._update_log, "✅ 執行完成")
        except asyncio.CancelledError:
            self.call_later(self._update_log, "⏹️ 作業已終止")
        except Exception as e:
            import traceback

            error_msg = f"❌ 執行失敗: {e}\n{traceback.format_exc()}"
            self.call_later(self._update_log, error_msg)
        finally:
            self._job_worker = None
            self._runtime.logger_manager.set_ui_sink(None)
            self.call_later(self._set_job_running_state, False)

    def _update_log(self, text: str) -> None:
        try:
            log = self.query_one("#log-output", Log)
            log.write_line(text)
        except Exception:
            pass

    def _set_job_running_state(self, is_running: bool) -> None:
        """Toggle Home action buttons based on execution state."""
        run_button = self.query_one("#run-jobs", Button)
        stop_button = self.query_one("#stop-jobs", Button)
        run_button.disabled = is_running
        stop_button.disabled = not is_running


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


class AddJobScreen(ModalScreen[dict | None]):
    """Modal screen for collecting a new job before writing config."""

    CSS = """
    AddJobScreen {
        align: center middle;
    }
    #add-job-dialog {
        width: 70;
        max-width: 90;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #add-job-actions {
        height: auto;
        margin-top: 1;
    }
    #add-job-error {
        color: $error;
        min-height: 2;
    }
    #add-job-plugins {
        height: 7;
    }
    """

    def __init__(
        self,
        plugin_options: list[str],
        defaults: dict | None = None,
    ):
        super().__init__()
        self._plugin_options = plugin_options
        self._defaults = defaults or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="add-job-dialog"):
            yield Static("➕ 新增 Job", id="add-job-title")
            yield Static("工作名稱", classes="add-job-label")
            yield Input(self._default_text("name"), id="add-job-name")
            yield Static("啟用", classes="add-job-label")
            yield Switch(value=self._default_bool("enable", True), id="add-job-enable")
            yield Static("Outlook 帳號", classes="add-job-label")
            yield Input(self._default_text("account"), id="add-job-account")
            yield Static("來源資料夾", classes="add-job-label")
            yield Input(self._default_text("source"), id="add-job-source")
            yield Static("目標資料夾（可留空）", classes="add-job-label")
            yield Input(self._default_text("destination"), id="add-job-destination")
            yield Static("處理上限", classes="add-job-label")
            yield Input(str(self._default_limit()), id="add-job-limit")
            yield Static("Plugins（可多選）", classes="add-job-label")
            default_plugins = set(self._default_plugins())
            yield SelectionList(
                *[
                    (
                        option,
                        option,
                        option in default_plugins,
                    )
                    for option in self._plugin_options
                ],
                id="add-job-plugins",
            )
            yield Static("", id="add-job-error")
            with Horizontal(id="add-job-actions"):
                yield Button("取消", id="add-job-cancel")
                yield Button("儲存 Job", id="add-job-save", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#add-job-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-job-cancel":
            self.dismiss(None)
            return
        if event.button.id == "add-job-save":
            self._submit()

    def _default_text(self, key: str) -> str:
        value = self._defaults.get(key, "")
        return str(value) if value is not None else ""

    def _default_bool(self, key: str, fallback: bool) -> bool:
        value = self._defaults.get(key)
        return bool(value) if isinstance(value, bool) else fallback

    def _default_limit(self) -> int:
        value = self._defaults.get("limit", 10)
        if isinstance(value, int) and value > 0:
            return value
        return 10

    def _default_plugins(self) -> list[str]:
        plugins = self._defaults.get("plugins", [])
        if isinstance(plugins, list):
            return [str(plugin).strip() for plugin in plugins if str(plugin).strip()]
        return []

    def _show_error(self, message: str) -> None:
        self.query_one("#add-job-error", Static).update(message)

    def _submit(self) -> None:
        name = self.query_one("#add-job-name", Input).value.strip()
        account = self.query_one("#add-job-account", Input).value.strip()
        source = self.query_one("#add-job-source", Input).value.strip()
        destination = self.query_one("#add-job-destination", Input).value.strip()
        limit_text = self.query_one("#add-job-limit", Input).value.strip()
        plugin_selector = self.query_one("#add-job-plugins", SelectionList)
        enable = self.query_one("#add-job-enable", Switch).value

        if not name:
            self._show_error("name 為必填")
            return
        if not account:
            self._show_error("account 為必填")
            return
        if not source:
            self._show_error("source 為必填")
            return

        try:
            limit = int(limit_text)
            if limit <= 0:
                raise ValueError
        except ValueError:
            self._show_error("limit 必須是正整數")
            return

        selected_plugins = set(plugin_selector.selected)
        plugins = [
            option for option in self._plugin_options if option in selected_plugins
        ]

        if "move_to_folder" in plugins and destination:
            self._show_error("使用 move_to_folder 時，請不要設定 destination")
            return

        job: dict[str, object] = {
            "name": name,
            "enable": enable,
            "account": account,
            "source": source,
            "limit": limit,
            "plugins": plugins,
        }
        if destination:
            job["destination"] = destination

        self.dismiss(job)


class PluginConfigEditorModal(ModalScreen[dict[str, Any] | None]):
    """Schema-driven plugin config editor modal."""

    CSS = """
    PluginConfigEditorModal {
        align: center middle;
    }
    #plugin-editor-dialog {
        width: 92;
        max-width: 120;
        height: 90%;
        min-height: 24;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #plugin-editor-form {
        height: 1fr;
        min-height: 8;
        margin-bottom: 1;
    }
    .plugin-field-label {
        margin-top: 1;
    }
    #plugin-editor-error {
        color: $error;
        min-height: 2;
    }
    #plugin-editor-actions {
        height: auto;
        margin-top: 1;
    }
    .plugin-select-field {
        height: 6;
    }
    .plugin-textarea-field {
        height: 7;
    }
    """

    def __init__(
        self,
        plugin_name: str,
        schema: dict[str, Any],
        current_config: dict[str, Any],
        entity_label: str = "Plugin",
    ):
        super().__init__()
        self._plugin_name = plugin_name
        self._entity_label = entity_label
        fields = schema.get("fields", {})
        self._fields = fields if isinstance(fields, dict) else {}
        buttons = schema.get("buttons", [])
        self._buttons = buttons if isinstance(buttons, list) else []
        rules = schema.get("validation_rules", [])
        self._rules = rules if isinstance(rules, list) else []
        self._current = current_config
        self._json_format_raw = self._extract_json_format_raw(current_config)
        self._json_format_examples, self._json_unparsed_keys = (
            self._parse_json_format_examples(self._json_format_raw)
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-editor-dialog"):
            yield Static(
                f"🧩 編輯 {self._entity_label}: {self._plugin_name}",
                id="plugin-editor-title",
            )
            with VerticalScroll(id="plugin-editor-form"):
                for field_name, spec in self._fields.items():
                    if not isinstance(spec, dict):
                        continue

                    required = bool(spec.get("required", False))
                    marker = " *" if required else ""
                    label = str(spec.get("label", field_name))
                    yield Static(f"{label}{marker}", classes="plugin-field-label")

                    field_type = str(spec.get("type", "str")).lower()
                    if field_type == "bool":
                        yield Switch(
                            value=self._resolve_initial_bool(field_name, spec),
                            id=self._widget_id(field_name),
                        )
                    elif field_type in {"select", "multiselect"}:
                        options = self._options(spec)
                        selected = self._resolve_initial_selection(field_name, spec)
                        yield SelectionList(
                            *[
                                (
                                    option,
                                    option,
                                    option in selected,
                                )
                                for option in options
                            ],
                            id=self._widget_id(field_name),
                            classes="plugin-select-field",
                        )
                    elif field_type in {"textarea", "list[str]", "list"}:
                        rows = spec.get("rows", 7)
                        try:
                            rows_value = int(rows)
                        except Exception:
                            rows_value = 7
                        textarea = TextArea(
                            self._resolve_initial_text(field_name, spec),
                            id=self._widget_id(field_name),
                            classes="plugin-textarea-field",
                        )
                        textarea.styles.height = max(4, min(rows_value + 1, 12))
                        yield textarea
                    elif field_type == "secret":
                        yield Input(
                            self._resolve_initial_text(field_name, spec),
                            placeholder=str(spec.get("placeholder", "")),
                            password=True,
                            id=self._widget_id(field_name),
                        )
                    else:
                        yield Input(
                            self._resolve_initial_text(field_name, spec),
                            placeholder=str(spec.get("placeholder", "")),
                            id=self._widget_id(field_name),
                        )

                if self._json_format_examples or self._json_unparsed_keys:
                    yield Static(
                        "JSON 輸出格式（時間欄位固定，其餘可改）",
                        classes="plugin-field-label",
                    )
                    for key, template in self._json_format_examples.items():
                        yield Static(f"{key}", classes="plugin-field-label")
                        for field_name, field_value in template.items():
                            locked = self._is_locked_json_field(field_name)
                            lock_suffix = " (固定)" if locked else ""
                            yield Static(
                                f"{field_name}{lock_suffix}",
                                classes="plugin-field-label",
                            )

                            if locked:
                                yield Static(str(field_value))
                                continue

                            widget_id = self._json_field_widget_id(key, field_name)
                            if isinstance(field_value, bool):
                                yield Switch(value=field_value, id=widget_id)
                            elif isinstance(field_value, list):
                                textarea = TextArea(
                                    "\n".join(str(item) for item in field_value),
                                    id=widget_id,
                                    classes="plugin-textarea-field",
                                )
                                textarea.styles.height = 5
                                yield textarea
                            else:
                                yield Input(str(field_value), id=widget_id)

                    if self._json_unparsed_keys:
                        names = ", ".join(self._json_unparsed_keys)
                        yield Static(
                            f"⚠️ 以下範例非 JSON 物件，保留原值: {names}",
                            classes="plugin-field-label",
                        )

            yield Static("", id="plugin-editor-error")
            with Horizontal(id="plugin-editor-actions"):
                yield Button("取消", id="plugin-editor-cancel")
                actions = self._schema_actions()
                if "validate" in actions:
                    yield Button(
                        "驗證",
                        id="plugin-editor-validate",
                        variant="warning",
                    )
                if "save" in actions:
                    yield Button("儲存", id="plugin-editor-save", variant="primary")

    def on_mount(self) -> None:
        first_field = next(iter(self._fields.keys()), None)
        if first_field is None:
            return

        widget_id = self._widget_id(first_field)
        try:
            self.query_one(f"#{widget_id}").focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "plugin-editor-cancel":
            self.dismiss(None)
            return

        try:
            payload = self._collect_payload()
        except ValueError as e:
            self._show_error(str(e))
            return

        has_error, has_warning, preview = self._evaluate_rule_result(payload)
        if event.button.id == "plugin-editor-validate":
            if has_error:
                self.app.notify(f"❌ 驗證失敗：{preview}", severity="error")
            elif has_warning:
                self.app.notify(f"⚠️ 驗證完成：{preview}", severity="warning")
            else:
                self.app.notify("✅ 驗證通過", severity="information")
            return

        if event.button.id == "plugin-editor-save":
            if has_error:
                self._show_error(preview)
                return
            if has_warning:
                self.app.notify(f"⚠️ 已儲存，請留意：{preview}", severity="warning")
            self.dismiss(payload)

    def _widget_id(self, field_name: str) -> str:
        return f"plugin-field-{field_name}"

    def _json_widget_id(self, key: str) -> str:
        safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
        return f"plugin-jsonfmt-{safe_key}"

    def _json_field_widget_id(self, key: str, field_name: str) -> str:
        safe_field = re.sub(r"[^a-zA-Z0-9_-]", "_", field_name)
        return f"{self._json_widget_id(key)}-{safe_field}"

    def _is_locked_json_field(self, field_name: str) -> bool:
        return field_name in {"action", "start", "end"}

    def _extract_json_format_raw(self, config: dict[str, Any]) -> dict[str, str]:
        json_format = config.get("response_json_format")
        if not isinstance(json_format, dict):
            return {}
        return {str(key): str(value) for key, value in json_format.items()}

    def _parse_json_format_examples(
        self,
        raw: dict[str, str],
    ) -> tuple[dict[str, dict[str, Any]], list[str]]:
        parsed: dict[str, dict[str, Any]] = {}
        unparsed: list[str] = []
        for key, value in raw.items():
            try:
                payload = json.loads(value)
            except json.JSONDecodeError:
                unparsed.append(key)
                continue
            if not isinstance(payload, dict):
                unparsed.append(key)
                continue
            parsed[key] = payload
        return parsed, unparsed

    def _schema_actions(self) -> set[str]:
        actions: set[str] = set()
        for button in self._buttons:
            if not isinstance(button, dict):
                continue
            action = str(button.get("action", "")).strip().lower()
            if action:
                actions.add(action)
        if not actions:
            return {"validate", "save"}
        return actions

    def _show_error(self, message: str) -> None:
        self.query_one("#plugin-editor-error", Static).update(message)

    def _options(self, spec: dict[str, Any]) -> list[str]:
        options = spec.get("options", [])
        if not isinstance(options, list):
            return []
        return [str(option) for option in options]

    def _resolve_default(self, field_name: str, spec: dict[str, Any]) -> Any:
        if field_name in self._current:
            return self._current[field_name]
        if "default" in spec:
            return spec["default"]

        field_type = str(spec.get("type", "str")).lower()
        if field_type == "bool":
            return False
        if field_type in {"int", "number"}:
            return 0
        if field_type in {"multiselect", "list", "list[str]"}:
            return []
        return ""

    def _resolve_initial_bool(self, field_name: str, spec: dict[str, Any]) -> bool:
        value = self._resolve_default(field_name, spec)
        return value if isinstance(value, bool) else bool(value)

    def _resolve_initial_text(self, field_name: str, spec: dict[str, Any]) -> str:
        value = self._resolve_default(field_name, spec)
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        if value is None:
            return ""
        return str(value)

    def _resolve_initial_selection(
        self,
        field_name: str,
        spec: dict[str, Any],
    ) -> set[str]:
        value = self._resolve_default(field_name, spec)
        field_type = str(spec.get("type", "select")).lower()
        options = set(self._options(spec))
        if field_type == "multiselect":
            if not isinstance(value, list):
                return set()
            return {str(item) for item in value if str(item) in options}

        selected = str(value) if value is not None else ""
        return {selected} if selected in options else set()

    def _collect_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field_name, spec in self._fields.items():
            if not isinstance(spec, dict):
                continue

            field_type = str(spec.get("type", "str")).lower()
            required = bool(spec.get("required", False))
            options = self._options(spec)
            field_label = str(spec.get("label", field_name))
            value: Any = None

            if field_type == "bool":
                value = self.query_one(f"#{self._widget_id(field_name)}", Switch).value
            elif field_type in {"select", "multiselect"}:
                selector = self.query_one(
                    f"#{self._widget_id(field_name)}",
                    SelectionList,
                )
                selected = [
                    option for option in options if option in set(selector.selected)
                ]
                if field_type == "select":
                    if required and not selected:
                        raise ValueError(f"{field_label} 為必填")
                    if len(selected) > 1:
                        raise ValueError(f"{field_label} 只能選一個選項")
                    value = selected[0] if selected else ""
                else:
                    value = selected
            elif field_type == "textarea":
                textarea_widget = self.query_one(
                    f"#{self._widget_id(field_name)}",
                    TextArea,
                )
                value = str(textarea_widget.text).strip()
            elif field_type in {"str", "path", "secret"}:
                input_widget = self.query_one(
                    f"#{self._widget_id(field_name)}",
                    Input,
                )
                value = input_widget.value.strip()
            elif field_type in {"list", "list[str]"}:
                textarea_widget = self.query_one(
                    f"#{self._widget_id(field_name)}",
                    TextArea,
                )
                lines = [line.strip() for line in textarea_widget.text.splitlines()]
                value = [line for line in lines if line]
            elif field_type in {"int", "number"}:
                input_widget = self.query_one(
                    f"#{self._widget_id(field_name)}",
                    Input,
                )
                text = input_widget.value.strip()
                if not text:
                    value = None
                else:
                    try:
                        value = int(text)
                    except ValueError as exc:
                        raise ValueError(f"{field_label} 必須是整數") from exc
            else:
                input_widget = self.query_one(
                    f"#{self._widget_id(field_name)}",
                    Input,
                )
                value = input_widget.value.strip()

            if required and (value is None or value == "" or value == []):
                raise ValueError(f"{field_label} 為必填")

            int_value = (
                value
                if isinstance(value, int) and not isinstance(value, bool)
                else None
            )
            if field_type in {"int", "number"} and int_value is not None:
                minimum = spec.get("min")
                maximum = spec.get("max")
                if isinstance(minimum, int) and int_value < minimum:
                    raise ValueError(f"{field_label} 不能小於 {minimum}")
                if isinstance(maximum, int) and int_value > maximum:
                    raise ValueError(f"{field_label} 不能大於 {maximum}")

            if field_type == "select" and value and value not in options:
                raise ValueError(f"{field_label} 選項不合法")

            if field_type == "multiselect" and isinstance(value, list):
                illegal = [item for item in value if item not in options]
                if illegal:
                    raise ValueError(
                        f"{field_label} 包含不合法選項: {', '.join(illegal)}"
                    )

            if value is not None:
                payload[field_name] = value

        if self._json_format_raw:
            response_json_format = dict(self._json_format_raw)
            for key, template in self._json_format_examples.items():
                rebuilt: dict[str, Any] = {}
                for field_name, original_value in template.items():
                    if self._is_locked_json_field(field_name):
                        rebuilt[field_name] = original_value
                        continue

                    widget_id = f"#{self._json_field_widget_id(key, field_name)}"
                    if isinstance(original_value, bool):
                        switch_widget = self.query_one(widget_id, Switch)
                        rebuilt[field_name] = bool(switch_widget.value)
                    elif isinstance(original_value, list):
                        textarea_widget = self.query_one(widget_id, TextArea)
                        lines = [
                            line.strip() for line in textarea_widget.text.splitlines()
                        ]
                        rebuilt[field_name] = [line for line in lines if line]
                    elif isinstance(original_value, int) and not isinstance(
                        original_value, bool
                    ):
                        input_widget = self.query_one(widget_id, Input)
                        text = input_widget.value.strip()
                        if not text:
                            raise ValueError(f"{key}.{field_name} 必須是整數")
                        try:
                            rebuilt[field_name] = int(text)
                        except ValueError as exc:
                            raise ValueError(f"{key}.{field_name} 必須是整數") from exc
                    elif isinstance(original_value, float):
                        input_widget = self.query_one(widget_id, Input)
                        text = input_widget.value.strip()
                        if not text:
                            raise ValueError(f"{key}.{field_name} 必須是數字")
                        try:
                            rebuilt[field_name] = float(text)
                        except ValueError as exc:
                            raise ValueError(f"{key}.{field_name} 必須是數字") from exc
                    else:
                        input_widget = self.query_one(widget_id, Input)
                        rebuilt[field_name] = input_widget.value.strip()

                response_json_format[key] = json.dumps(rebuilt, ensure_ascii=False)

            payload["response_json_format"] = response_json_format

        return payload

    def _evaluate_rule_result(self, payload: dict[str, Any]) -> tuple[bool, bool, str]:
        results = evaluate_rules(payload, self._rules)
        failed_errors: list[str] = []
        failed_warnings: list[str] = []
        for result in results:
            if result.passed:
                continue
            if result.level == "error":
                failed_errors.append(result.message)
            else:
                failed_warnings.append(result.message)

        if failed_errors:
            return True, bool(failed_warnings), "；".join(failed_errors[:2])
        if failed_warnings:
            return False, True, "；".join(failed_warnings[:2])
        return False, False, ""


class MainConfigTab(Static):
    """一般設定分頁"""

    CSS = """
    #main-config-split {
        height: 100%;
    }
    #main-jobs-pane {
        height: auto;
        min-height: 3;
    }
    #main-jobs-table {
        height: auto;
    }
    #main-schema-pane {
        layout: vertical;
        height: 1fr;
        border-top: solid $accent;
        padding-top: 0;
    }
    #main-schema-actions {
        height: auto;
        min-height: 4;
        margin-bottom: 0;
        padding: 0 0 1 0;
    }
    #main-schema-actions Button {
        height: auto;
        min-height: 3;
    }
    #main-config-title {
        margin-top: 0;
    }
    #main-config-content {
        height: 1fr;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        self._sample_path = self._runtime.paths.config_dir / "config.yaml.sample"
        self._ui_schema = load_ui_schema(self._sample_path)
        self._schema_errors = validate_ui_schema(self._ui_schema)
        self._reset_armed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="main-config-split"):
            with Vertical(id="main-jobs-pane"):
                yield Static("📋 Jobs 清單", id="main-jobs-title")
                yield DataTable(id="main-jobs-table")

            with Vertical(id="main-schema-pane"):
                with Horizontal(id="main-schema-actions"):
                    for button in self._ui_schema.get("buttons", []):
                        if not isinstance(button, dict):
                            continue
                        btn = Button(
                            str(button.get("label", "未命名按鈕")),
                            id=f"schema-btn-{button.get('id', 'unknown')}",
                            variant=self._resolve_button_variant(
                                str(button.get("variant", "default"))
                            ),
                        )
                        btn.styles.min_height = 5
                        btn.styles.height = "auto"
                        yield btn
                yield Static("📄 主設定檔 (config/config.yaml)", id="main-config-title")
                yield TextArea("", id="main-config-content", read_only=False)

    def on_mount(self) -> None:
        actions = self.query_one("#main-schema-actions", Horizontal)
        actions.styles.min_height = 6
        actions.styles.height = "auto"
        self._load_config()

    def _resolve_button_variant(
        self,
        variant: str,
    ) -> Literal["default", "primary", "success", "warning", "error"]:
        mapping: dict[
            str,
            Literal["default", "primary", "success", "warning", "error"],
        ] = {
            "primary": "primary",
            "success": "success",
            "warning": "warning",
            "error": "error",
            "default": "default",
        }
        return mapping.get(variant, "default")

    def _render_jobs_table(self, config: dict) -> None:
        jobs_pane = self.query_one("#main-jobs-pane", Vertical)
        table = self.query_one("#main-jobs-table", DataTable)
        table.clear(columns=True)
        table.add_columns("啟用", "名稱", "帳號", "來源", "目標", "Plugins", "Limit")

        jobs = config.get("jobs", [])
        if not isinstance(jobs, list):
            table.styles.height = 4
            jobs_pane.styles.height = 6
            return

        rendered_rows = 0
        for job in jobs:
            if not isinstance(job, dict):
                continue
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
            rendered_rows += 1

        visible_rows = max(2, min(rendered_rows + 1, 6))
        table.styles.height = visible_rows
        jobs_pane.styles.height = visible_rows + 2

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not event.button.id or not event.button.id.startswith("schema-btn-"):
            return

        action = event.button.id.removeprefix("schema-btn-")
        if action == "validate":
            self._run_schema_validation()
            return
        if action == "save":
            self._save_from_editor()
            return
        if action == "add_job":
            self._add_job()
            return
        if action == "remove_job":
            self._remove_job()
            return
        if action == "reset":
            self._reset_from_sample()
            return

        self.app.notify(
            f"此按鈕尚未接上編輯流程: {action} (目前提供 schema 預覽與驗證)",
            severity="warning",
        )

    def _load_raw_config(self) -> dict:
        config_path = self._runtime.paths.config_file
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("config.yaml 內容必須是物件")
        return data

    def _load_editor_config(self) -> dict:
        content_widget = self.query_one("#main-config-content", TextArea)
        data = yaml.safe_load(content_widget.text) or {}
        if not isinstance(data, dict):
            raise ValueError("設定內容必須是 YAML 物件")
        return data

    def _dump_editor_config(self, data: dict) -> None:
        content_widget = self.query_one("#main-config-content", TextArea)
        content_widget.load_text(
            yaml.safe_dump(
                data,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
        )

    def _write_config_file(self, data: dict) -> None:
        config_path = self._runtime.paths.config_file
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(
                data,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )

    def _save_from_editor(self) -> None:
        try:
            config = self._load_editor_config()
            sanitized = strip_reserved_metadata(config)
            self._write_config_file(sanitized)
            self._dump_editor_config(sanitized)
            self._load_config()
            self._run_schema_validation()
            self._reset_armed = False
            self.app.notify("✅ 已儲存 config/config.yaml", severity="information")
        except Exception as e:
            self.app.notify(f"❌ 儲存失敗: {e}", severity="error")

    def _next_job_name(self, jobs: list[dict]) -> str:
        existing = {str(job.get("name", "")).strip() for job in jobs}
        index = 1
        while True:
            candidate = f"新工作{index}"
            if candidate not in existing:
                return candidate
            index += 1

    def _plugin_options_from_schema(self) -> list[str]:
        fields = self._ui_schema.get("fields", {})
        if not isinstance(fields, dict):
            return []

        jobs = fields.get("jobs", {})
        if not isinstance(jobs, dict):
            return []

        item_fields = jobs.get("item_fields", {})
        if not isinstance(item_fields, dict):
            return []

        plugins = item_fields.get("plugins", {})
        if not isinstance(plugins, dict):
            return []

        options = plugins.get("options", [])
        if not isinstance(options, list):
            return []

        return [str(option) for option in options]

    def _handle_add_job_result(self, result: dict | None) -> None:
        if result is None:
            return

        try:
            config = self._load_editor_config()
            jobs = config.get("jobs", [])
            if not isinstance(jobs, list):
                raise ValueError("jobs 必須是陣列")

            existing_names = {
                str(job.get("name", "")).strip()
                for job in jobs
                if isinstance(job, dict)
            }
            new_name = str(result.get("name", "")).strip()
            if new_name in existing_names:
                raise ValueError(f"Job 名稱重複: {new_name}")

            jobs.append(result)
            config["jobs"] = jobs
            self._dump_editor_config(config)
            self._run_schema_validation()
            self._render_jobs_table(config)
            self._reset_armed = False
            self.app.notify("✅ 已新增一筆 Job 到編輯器", severity="information")
        except Exception as e:
            self.app.notify(f"❌ 新增 Job 失敗: {e}", severity="error")

    def _add_job(self) -> None:
        defaults = build_default_list_item(self._ui_schema, "jobs")
        plugin_options = self._plugin_options_from_schema()

        try:
            config = self._load_editor_config()
            jobs = config.get("jobs", [])
            if isinstance(jobs, list) and jobs:
                if not str(defaults.get("name", "")).strip():
                    defaults["name"] = self._next_job_name(
                        [j for j in jobs if isinstance(j, dict)]
                    )
        except Exception:
            defaults.setdefault("name", "新工作1")

        self.app.push_screen(
            AddJobScreen(plugin_options=plugin_options, defaults=defaults),
            self._handle_add_job_result,
        )

    def _remove_job(self) -> None:
        try:
            config = self._load_editor_config()
            jobs = config.get("jobs", [])
            if not isinstance(jobs, list):
                raise ValueError("jobs 必須是陣列")
            if not jobs:
                self.app.notify("⚠️ 沒有可刪除的 Job", severity="warning")
                return

            removed = jobs.pop()
            config["jobs"] = jobs
            self._dump_editor_config(config)
            self._run_schema_validation()
            self._render_jobs_table(config)
            self._reset_armed = False
            name = (
                str(removed.get("name", "(未命名)"))
                if isinstance(removed, dict)
                else "(未知)"
            )
            self.app.notify(f"✅ 已刪除最後一筆 Job: {name}", severity="information")
        except Exception as e:
            self.app.notify(f"❌ 刪除 Job 失敗: {e}", severity="error")

    def _reset_from_sample(self) -> None:
        if not self._reset_armed:
            self._reset_armed = True
            self.app.notify(
                "⚠️ 再按一次「回復範本」以確認覆蓋目前編輯內容",
                severity="warning",
            )
            return

        try:
            with open(self._sample_path, encoding="utf-8") as f:
                sample = yaml.safe_load(f) or {}
            if not isinstance(sample, dict):
                raise ValueError("sample 內容格式錯誤")

            sanitized = strip_reserved_metadata(sample)
            self._dump_editor_config(sanitized)
            self._write_config_file(sanitized)
            self._load_config()
            self._run_schema_validation()
            self.app.notify("✅ 已用 sample 回復設定", severity="information")
        except Exception as e:
            self.app.notify(f"❌ 回復失敗: {e}", severity="error")
        finally:
            self._reset_armed = False

    def _run_schema_validation(self, use_editor: bool = True) -> None:
        if self._schema_errors:
            preview = " | ".join(self._schema_errors[:2])
            self.app.notify(
                f"❌ _ui schema 結構錯誤: {preview}",
                severity="error",
            )
            return

        try:
            if use_editor:
                config = self._load_editor_config()
            else:
                config_path = self._runtime.paths.config_file
                if not config_path.exists():
                    self.app.notify("❌ 找不到 config/config.yaml", severity="error")
                    return
                config = self._load_raw_config()
            results = evaluate_rules(
                config,
                self._ui_schema.get("validation_rules", []),
            )
        except Exception as e:
            self.app.notify(f"❌ YAML 解析失敗: {e}", severity="error")
            return

        has_error = False
        has_warning = False
        failed_errors: list[str] = []
        failed_warnings: list[str] = []
        for result in results:
            if not result.passed:
                if result.level == "error":
                    has_error = True
                    failed_errors.append(result.message)
                else:
                    has_warning = True
                    failed_warnings.append(result.message)

        if has_error:
            detail = "；".join(failed_errors[:2])
            self.app.notify(
                f"❌ 驗證失敗：{detail}",
                severity="error",
            )
        elif has_warning:
            detail = "；".join(failed_warnings[:2])
            self.app.notify(
                f"⚠️ 驗證完成：{detail}",
                severity="warning",
            )
        else:
            self.app.notify("✅ 驗證通過", severity="information")

    def _load_config(self) -> None:
        content_widget = self.query_one("#main-config-content", TextArea)
        table = self.query_one("#main-jobs-table", DataTable)
        table.clear(columns=True)

        config_path = self._runtime.paths.config_file
        if not config_path.exists():
            content_widget.load_text(
                "⚠️ 找不到 config/config.yaml\n\n請先到 About 分頁按「初始化設定」。"
            )
            self.query_one("#main-config-title", Static).update(
                "📄 主設定檔 (config/config.yaml) ⚠️ 尚未初始化"
            )
            return

        try:
            content = config_path.read_text(encoding="utf-8")
            content_widget.load_text(content)

            config = load_config(config_path)
            self._render_jobs_table(config)

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

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        self._sample_path = self._runtime.paths.llm_config_file.with_suffix(
            ".yaml.sample"
        )
        self._ui_schema = load_ui_schema(self._sample_path)
        self._schema_errors = validate_ui_schema(self._ui_schema)

    def compose(self) -> ComposeResult:
        with Vertical(id="llm-main"):
            yield Static("🤖 LLM 設定 (config/llm-config.yaml)", id="llm-config-title")
            yield TextArea("", id="llm-config-content", read_only=True)
            yield Static("📊 設定值", id="llm-values-title")
            yield DataTable(id="llm-table")
            yield Static("💡 說明", id="llm-help-title")
            yield Static(
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
                yield Button("🛠️ 編輯設定", id="edit-llm-config")

    def on_mount(self) -> None:
        self._load_llm_config()

    def _load_llm_config(self) -> None:
        content_widget = self.query_one("#llm-config-content", TextArea)
        table = self.query_one("#llm-table", DataTable)

        try:
            llm_config_path = self._runtime.paths.llm_config_file
            content = llm_config_path.read_text(encoding="utf-8")
            masked_content = re.sub(r"(api_key:\s*).+", r"\1***", content)
            content_widget.load_text(masked_content)

            llm_config = load_llm_config(str(llm_config_path))
            table.clear()
            table.add_columns("項目", "值")
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
            return
        if event.button.id == "edit-llm-config":
            self._open_llm_editor()

    def _load_llm_payload(self) -> dict[str, Any]:
        llm_config_path = self._runtime.paths.llm_config_file
        if not llm_config_path.exists():
            raise FileNotFoundError("找不到 config/llm-config.yaml")

        try:
            with open(llm_config_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"llm-config.yaml YAML 解析錯誤: {e}") from e

        if not isinstance(payload, dict):
            raise ValueError("llm-config.yaml 內容必須是 YAML 物件")
        return payload

    def _open_llm_editor(self) -> None:
        if not self._ui_schema:
            self.app.notify(
                "⚠️ llm-config.yaml.sample 缺少 _ui，維持唯讀模式", severity="warning"
            )
            return

        if self._schema_errors:
            preview = " | ".join(self._schema_errors[:2])
            self.app.notify(f"❌ _ui schema 結構錯誤: {preview}", severity="error")
            return

        try:
            payload = self._load_llm_payload()
        except Exception as e:
            self.app.notify(str(e), severity="error")
            return

        self.app.push_screen(
            PluginConfigEditorModal(
                plugin_name="llm-config",
                schema=self._ui_schema,
                current_config=strip_reserved_metadata(payload),
                entity_label="LLM",
            ),
            self._handle_llm_editor_result,
        )

    def _handle_llm_editor_result(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return

        sanitized = strip_reserved_metadata(result)
        results = evaluate_rules(sanitized, self._ui_schema.get("validation_rules", []))
        failed_errors = [
            r.message for r in results if not r.passed and r.level == "error"
        ]
        failed_warnings = [
            r.message for r in results if not r.passed and r.level != "error"
        ]

        if failed_errors:
            preview = "；".join(failed_errors[:2])
            self.app.notify(f"❌ 驗證失敗：{preview}", severity="error")
            return

        try:
            self._write_llm_config_file(sanitized)
            self._load_llm_config()
            if failed_warnings:
                preview = "；".join(failed_warnings[:2])
                self.app.notify(f"⚠️ 已儲存，請留意：{preview}", severity="warning")
            else:
                self.app.notify("✅ 已儲存 llm-config.yaml", severity="information")
        except Exception as e:
            self.app.notify(f"❌ 儲存失敗: {e}", severity="error")

    def _write_llm_config_file(self, payload: dict[str, Any]) -> Path:
        """Write LLM config and create `.bak` when original exists."""
        llm_config_path = self._runtime.paths.llm_config_file
        llm_config_path.parent.mkdir(parents=True, exist_ok=True)
        if llm_config_path.exists():
            backup_path = llm_config_path.with_suffix(".yaml.bak")
            backup_path.write_text(
                llm_config_path.read_text(encoding="utf-8"), encoding="utf-8"
            )

        llm_config_path.write_text(
            yaml.safe_dump(
                payload,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
        return llm_config_path

    def _test_llm_connection(self) -> None:
        llm_config_path = self._runtime.paths.llm_config_file
        if not llm_config_path.exists():
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
            llm_config = load_llm_config(str(self._runtime.paths.llm_config_file))
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

    CSS = """
    #plugin-actions {
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        self._selected_plugin: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="plugin-main"):
            yield Static("📦 Plugins", id="plugin-list-title")
            yield DataTable(id="plugin-list", show_cursor=True, cursor_type="row")
            with Horizontal(id="plugin-actions"):
                yield Button("🔄 重新整理", id="refresh-plugins", variant="primary")
                yield Button("🛠️ 編輯設定", id="edit-plugin", disabled=True)
            yield Static("📄 選取的 Plugin 設定", id="plugin-content-title")
            yield TextArea("", id="plugin-content", read_only=True)

    def on_mount(self) -> None:
        self._load_plugins()

    def on_show(self) -> None:
        self._load_plugins()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-plugins":
            self._load_plugins()
            return
        if event.button.id == "edit-plugin":
            self._open_plugin_editor()

    def _load_plugins(self) -> None:
        title = self.query_one("#plugin-list-title", Static)
        table = self.query_one("#plugin-list", DataTable)
        edit_button = self.query_one("#edit-plugin", Button)

        table.clear()
        table.add_columns("Plugin 名稱", "狀態")
        self._selected_plugin = None
        edit_button.disabled = True

        plugins_dir = self._runtime.paths.plugins_dir
        if not plugins_dir.exists():
            title.update("📦 Plugins (目錄不存在)")
            table.add_row("❌ plugins 目錄不存在", "")
            return

        plugin_files = sorted(plugins_dir.glob("*.yaml*"))

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
            self._selected_plugin = str(plugin_name)
            self.query_one("#edit-plugin", Button).disabled = False
            self._load_plugin_content(plugin_name)

    def _load_plugin_content(self, plugin_name: str) -> None:
        content_widget = self.query_one("#plugin-content", TextArea)

        plugins_dir = self._runtime.paths.plugins_dir
        sample_path = plugins_dir / f"{plugin_name}.yaml.sample"
        normal_path = plugins_dir / f"{plugin_name}.yaml"

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

    def _plugin_paths(self, plugin_name: str) -> tuple[Path, Path]:
        plugins_dir = self._runtime.paths.plugins_dir
        sample_path = plugins_dir / f"{plugin_name}.yaml.sample"
        normal_path = plugins_dir / f"{plugin_name}.yaml"
        return sample_path, normal_path

    def _load_plugin_payload(self, plugin_name: str) -> tuple[dict[str, Any], Path]:
        sample_path, normal_path = self._plugin_paths(plugin_name)
        file_path = normal_path if normal_path.exists() else sample_path
        if not file_path.exists():
            raise FileNotFoundError(f"找不到 {plugin_name}.yaml 或 sample")

        try:
            with open(file_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"{file_path.name} YAML 解析錯誤: {e}") from e

        if not isinstance(payload, dict):
            raise ValueError(f"{file_path.name} 內容必須是 YAML 物件")
        return payload, file_path

    def _open_plugin_editor(self) -> None:
        plugin_name = self._selected_plugin
        if not plugin_name:
            self.app.notify("⚠️ 請先選擇一個 Plugin", severity="warning")
            return

        schema = load_plugin_ui_schema(plugin_name, self._runtime.paths.plugins_dir)
        if not schema:
            self.app.notify(
                f"⚠️ {plugin_name}.yaml.sample 缺少 _ui，回退為唯讀模式",
                severity="warning",
            )
            return

        schema_errors = validate_ui_schema(schema)
        if schema_errors:
            preview = " | ".join(schema_errors[:2])
            self.app.notify(f"❌ _ui schema 結構錯誤: {preview}", severity="error")
            return

        try:
            payload, _ = self._load_plugin_payload(plugin_name)
        except Exception as e:
            self.app.notify(str(e), severity="error")
            return

        self.app.push_screen(
            PluginConfigEditorModal(
                plugin_name=plugin_name,
                schema=schema,
                current_config=strip_reserved_metadata(payload),
            ),
            self._handle_plugin_editor_result,
        )

    def _handle_plugin_editor_result(self, result: dict[str, Any] | None) -> None:
        if result is None:
            return

        plugin_name = self._selected_plugin
        if not plugin_name:
            return

        sanitized = strip_reserved_metadata(result)

        try:
            self._write_plugin_config_file(plugin_name, sanitized)
            self._load_plugins()
            self._selected_plugin = plugin_name
            self._load_plugin_content(plugin_name)
            self.query_one("#edit-plugin", Button).disabled = False
            self.app.notify(f"✅ 已儲存 {plugin_name}.yaml", severity="information")
        except Exception as e:
            self.app.notify(f"❌ 儲存失敗: {e}", severity="error")

    def _write_plugin_config_file(
        self,
        plugin_name: str,
        payload: dict[str, Any],
    ) -> Path:
        """Write plugin config and create `.bak` when original exists."""
        _, normal_path = self._plugin_paths(plugin_name)
        normal_path.parent.mkdir(parents=True, exist_ok=True)
        if normal_path.exists():
            backup_path = normal_path.parent / f"{plugin_name}.yaml.bak"
            backup_path.write_text(
                normal_path.read_text(encoding="utf-8"), encoding="utf-8"
            )

        normal_path.write_text(
            yaml.safe_dump(
                payload,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
        return normal_path


class ConfigScreen(Static):
    """Configuration 標籤頁 - 設定檔檢視"""

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="main"):
            with TabPane("一般設定", id="main"):
                yield MainConfigTab(runtime_context=self._runtime)
            with TabPane("LLM 設定", id="llm"):
                yield LLMConfigTab(runtime_context=self._runtime)
            with TabPane("Plugin 設定", id="plugins"):
                yield PluginsConfigTab(runtime_context=self._runtime)
