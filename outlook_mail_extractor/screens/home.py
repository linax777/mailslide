"""Home tab screen."""

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Log, Static
from textual.worker import Worker

from ..config import load_config
from ..core import OutlookConnectionError
from ..runtime import RuntimeContext, get_runtime_context
from ..services.job_execution import JobExecutionService
from ..services.preflight import PreflightCheckService
from .common import truncate


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
