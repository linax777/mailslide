"""Schedule tab screen."""

from datetime import datetime

import pycron
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widgets import Input, Log, Static, Switch
from textual.containers import Vertical

from ..i18n import t
from .home import HomeScreen


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
            yield Static(t("ui.schedule.title"), id="schedule-title")
            with Vertical(id="schedule-toggle"):
                yield Static(t("ui.schedule.enable"), id="schedule-enable-label")
                yield Switch(id="schedule-switch")
            with Vertical(id="schedule-cron"):
                yield Static(t("ui.schedule.cron_label"), id="cron-label")
                yield Input("0 * * * *", id="cron-input", placeholder="* * * * *")
            yield Static(t("ui.schedule.examples.title"), id="examples-title")
            yield Static(t("ui.schedule.examples.content"), id="examples-content")
            yield Static(t("ui.schedule.log.title"), id="log-title")
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
            self._show_error(t("ui.schedule.error.cron_field_count", count=len(parts)))
            return False

        field_names = [
            t("ui.schedule.field.minute"),
            t("ui.schedule.field.hour"),
            t("ui.schedule.field.day"),
            t("ui.schedule.field.month"),
            t("ui.schedule.field.weekday"),
        ]
        valid_ranges = [
            (0, 59),
            (0, 23),
            (1, 31),
            (1, 12),
            (0, 6),
        ]

        for i, (part, name, (min_val, max_val)) in enumerate(
            zip(parts, field_names, valid_ranges)
        ):
            if not self._validate_cron_field(part, min_val, max_val):
                self._show_error(
                    t(
                        "ui.schedule.error.cron_field_invalid",
                        index=i + 1,
                        field=name,
                        value=part,
                    )
                )
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
        self._log(t("ui.schedule.log.enabled", expr=self._cron_expression))

    def _stop_scheduler(self) -> None:
        if self._schedule_timer is not None:
            self._schedule_timer.stop()
            self._schedule_timer = None
        self._log(t("ui.schedule.log.disabled"))

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
                    self._log(
                        t(
                            "ui.schedule.log.triggered",
                            time=now.strftime("%H:%M"),
                        )
                    )
                    self._run_jobs()
        except Exception as e:
            self._log(t("ui.schedule.error.check_failed", error=e))

    def _run_jobs(self) -> None:
        try:
            home_screen = self.app.query_one(HomeScreen)
            home_screen.run_jobs()
        except Exception as e:
            self._log(t("ui.schedule.error.execution_failed", error=e))

    def _log(self, message: str) -> None:
        try:
            log_widget = self.query_one("#log-output", Log)
            log_widget.write_line(message)
        except Exception:
            pass
