"""Home tab screen."""

import asyncio

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Button, DataTable, Log, Static
from textual.worker import NoActiveWorker, Worker, get_current_worker

from ..config import get_last_migration_result, load_config
from ..contracts.dependency_guard import (
    DEPENDENCY_GUARD_REASON,
    DEPENDENCY_GUARD_TERMINAL_STATUS,
)
from ..core import OutlookConnectionError
from ..i18n import resolve_language, set_language, t
from ..models import DependencyGuardError
from ..runtime import RuntimeContext, get_runtime_context
from ..services.job_execution import JobExecutionService
from ..services.preflight import PreflightCheckService
from .common import truncate


FRAME_1 = """  [@]"
=#=#=#=#"""

FRAME_2 = """  [@]'
#=#=#=#="""


class HomeScreen(Static):
    """Home 標籤頁 - 執行 Jobs"""

    CSS = """
    #home-actions {
        height: auto;
    }
    #jobs-animation {
        height: auto;
        width: 100%;
    }
    #toggle-preserve-reply-thread {
        margin: 0 0 0 2;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        set_language(resolve_language(self._runtime.paths.config_file))
        self._scheduler_enabled = False
        self._cron_expression = "0 * * * *"
        self._last_run_time = None
        self._polling = False
        self._preserve_reply_thread = True
        self._job_worker: Worker | None = None
        self._job_terminal_status: str | None = None
        self._animation_timer: Timer | None = None
        self._animation_frame_idx = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="home-container"):
            yield Static(
                t("ui.home.help"),
                id="help-text",
            )
            yield Static("", id="home-status")
            with Horizontal(id="home-actions"):
                yield Button(t("ui.home.button.run"), id="run-jobs", variant="primary")
                yield Button(
                    t("ui.home.button.stop"),
                    id="stop-jobs",
                    variant="error",
                    disabled=True,
                )
                yield Button(t("ui.home.button.refresh"), id="refresh-jobs")
                yield Button(
                    t("ui.home.button.preserve.on"),
                    id="toggle-preserve-reply-thread",
                    variant="default",
                )
            yield Static(t("ui.home.jobs.title"), id="jobs-title")
            yield Static("", id="jobs-animation")
            yield DataTable(id="jobs-table")
            yield Static(t("ui.home.log.title"), id="log-title")
            yield Log(id="log-output", auto_scroll=True)

    def on_mount(self) -> None:
        self._update_preserve_reply_button()
        self._load_jobs()

    def on_unmount(self) -> None:
        self._stop_jobs_animation()

    def _load_jobs(self) -> None:
        table = self.query_one("#jobs-table", DataTable)
        status = self.query_one("#home-status", Static)
        run_button = self.query_one("#run-jobs", Button)
        table.clear(columns=True)

        config_path = self._runtime.paths.config_file
        if not config_path.exists():
            status.update(t("ui.home.status.not_initialized"))
            table.add_columns(
                t("ui.common.column.status"), t("ui.common.column.detail")
            )
            table.add_row(
                t("ui.home.row.uninitialized"),
                t("ui.home.row.config_missing"),
            )
            run_button.disabled = True
            return

        try:
            config = load_config(config_path)
            migration_result = get_last_migration_result()
            if migration_result and migration_result.changed:
                backup = (
                    str(migration_result.backup_path)
                    if migration_result.backup_path
                    else "-"
                )
                self.app.notify(
                    t(
                        "ui.config.migration.applied",
                        from_version=migration_result.from_version,
                        to_version=migration_result.to_version,
                        backup=backup,
                    ),
                    severity="information",
                )
            status.update("")
            table.add_columns(
                "#",
                t("ui.home.column.enabled"),
                t("ui.home.column.name"),
                t("ui.home.column.account"),
                t("ui.home.column.source"),
                t("ui.home.column.destination"),
                t("ui.home.column.plugins"),
            )
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
            status.update(t("ui.home.status.config_invalid"))
            table.add_columns(
                t("ui.common.column.status"), t("ui.common.column.detail")
            )
            table.add_row(t("ui.home.row.load_failed"), str(e))
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
            status = (
                t("ui.home.preserve.enabled")
                if self._preserve_reply_thread
                else t("ui.home.preserve.disabled")
            )
            self.app.notify(
                t("ui.home.notify.preserve_updated", status=status),
                severity="information",
            )

    def _update_preserve_reply_button(self) -> None:
        """Update preserve-reply-thread toggle button label."""
        button = self.query_one("#toggle-preserve-reply-thread", Button)
        button.label = (
            t("ui.home.button.preserve.on")
            if self._preserve_reply_thread
            else t("ui.home.button.preserve.off")
        )

    def run_jobs(self) -> None:
        if self._job_worker and self._job_worker.is_running:
            self.app.notify(t("ui.home.notify.already_running"), severity="warning")
            return

        if not self._validate_jobs_before_run():
            return

        log_widget = self.query_one("#log-output", Log)
        log_widget.clear()

        def ui_sink(message: str) -> None:
            self.app.call_from_thread(log_widget.write_line, message)

        self._runtime.logger_manager.set_ui_sink(ui_sink)
        self._runtime.logger_manager.start_session(enable_ui_sink=True)
        self._job_terminal_status = None

        self._set_job_running_state(True)
        self._job_worker = self.run_worker(
            self._execute_jobs(),
            exclusive=True,
            thread=True,
        )

    def stop_jobs(self) -> None:
        """Request cancellation for the current job worker."""
        if not self._job_worker or not self._job_worker.is_running:
            self.app.notify(t("ui.home.notify.no_running_job"), severity="information")
            self._set_job_running_state(False)
            return

        self._job_worker.cancel()
        self._update_log(t("ui.home.log.stop_requested"))
        self.app.notify(t("ui.home.notify.stop_requested"), severity="warning")

        stop_button = self.query_one("#stop-jobs", Button)
        stop_button.disabled = True

    def _validate_jobs_before_run(self) -> bool:
        """Validate enabled jobs before starting execution."""
        try:
            config = load_config(self._runtime.paths.config_file)
        except Exception as e:
            self.app.notify(t("ui.home.error.config_load", error=e), severity="error")
            return False

        enabled_jobs = [
            job for job in config.get("jobs", []) if job.get("enable", True)
        ]
        if not enabled_jobs:
            self.app.notify(t("ui.home.notify.no_enabled_jobs"), severity="warning")
            return False

        try:
            preflight = PreflightCheckService(
                client_factory=self._runtime.client_factory,
            )
            result = preflight.run(
                {"jobs": enabled_jobs},
            )
        except OutlookConnectionError as e:
            self.app.notify(
                t("ui.home.error.outlook_connect", error=e), severity="error"
            )
            return False
        except Exception as e:
            self.app.notify(t("ui.home.error.preflight", error=e), severity="error")
            return False

        if result.issues:
            for issue in result.issues[:3]:
                self.app.notify(
                    t("ui.home.error.preflight_issue", issue=issue), severity="error"
                )
            if len(result.issues) > 3:
                self.app.notify(
                    t(
                        "ui.home.error.preflight_more_issues",
                        count=len(result.issues) - 3,
                    ),
                    severity="error",
                )
            return False

        return True

    async def _execute_jobs(self) -> None:
        current_worker: Worker | None = None
        try:
            current_worker = get_current_worker()
        except NoActiveWorker:
            current_worker = None

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
                cancel_requested=(
                    current_worker.cancelled_event.is_set if current_worker else None
                ),
            )
            self._job_terminal_status = "success"
            self.call_later(self._update_log, t("ui.home.log.done"))
        except asyncio.CancelledError:
            self._job_terminal_status = "cancelled"
            self.call_later(self._update_log, t("ui.home.log.cancelled"))
        except DependencyGuardError as e:
            self._job_terminal_status = DEPENDENCY_GUARD_TERMINAL_STATUS
            self.call_later(
                self._update_log,
                t(
                    "ui.home.log.dependency_guard_failed",
                    status=DEPENDENCY_GUARD_TERMINAL_STATUS,
                    reason=DEPENDENCY_GUARD_REASON,
                    error=e,
                ),
            )
        except Exception as e:
            import traceback

            self._job_terminal_status = "failed"
            error_msg = (
                f"{t('ui.home.error.execution_failed', error=e)}\n"
                f"{traceback.format_exc()}"
            )
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
        if is_running:
            self._start_jobs_animation()
        else:
            self._stop_jobs_animation()

    def _start_jobs_animation(self) -> None:
        if self._animation_timer is not None:
            return
        self._animation_frame_idx = 0
        self._render_jobs_animation()
        self._animation_timer = self.set_interval(0.5, self._advance_jobs_animation)

    def _stop_jobs_animation(self) -> None:
        if self._animation_timer is not None:
            self._animation_timer.stop()
            self._animation_timer = None
        self._animation_frame_idx = 0
        try:
            animation = self.query_one("#jobs-animation", Static)
            animation.update("")
        except Exception:
            pass

    def _advance_jobs_animation(self) -> None:
        self._animation_frame_idx = 1 - self._animation_frame_idx
        self._render_jobs_animation()

    def _render_jobs_animation(self) -> None:
        frame = FRAME_1 if self._animation_frame_idx == 0 else FRAME_2
        try:
            animation = self.query_one("#jobs-animation", Static)
            width = animation.content_region.width
            if width <= 0:
                animation.update(Text(frame))
                return

            lines = frame.splitlines()
            block_width = max((len(line) for line in lines), default=0)
            left_padding = max(width - block_width, 0)
            prefix = " " * left_padding
            padded = "\n".join(f"{prefix}{line}" for line in lines)
            animation.update(Text(padded))
        except Exception:
            pass
