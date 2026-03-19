"""Schedule tab screen."""

from datetime import datetime

import pycron
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widgets import Input, Log, Static, Switch
from textual.containers import Vertical

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
