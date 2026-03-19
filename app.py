"""Outlook Mail Extractor - 應用程式入口"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Middle
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, TabbedContent, TabPane

from outlook_mail_extractor.screens import (
    AboutScreen,
    ConfigScreen,
    HomeScreen,
    ScheduleScreen,
    UsageScreen,
)
from outlook_mail_extractor.runtime import get_runtime_context


class ConfirmScreen(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield Label("確定要結束程式嗎？\n")
                with Horizontal():
                    yield Button("確定", variant="error", id="yes")
                    yield Button("取消", variant="primary", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class OutlookMailExtractor(App):
    BINDINGS = [
        Binding("h", "show_tab('home')", "Home"),
        Binding("s", "show_tab('schedule')", "Schedule"),
        Binding("g", "show_tab('usage')", "Guide"),
        Binding("c", "show_tab('config')", "Config"),
        Binding("a", "show_tab('about')", "About"),
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding(key="q", action="confirm_quit", description="Quit the app"),
    ]

    def compose(self) -> ComposeResult:
        runtime = get_runtime_context()
        yield Header()
        yield Footer()
        with TabbedContent(initial="home"):
            with TabPane("Home", id="home"):
                yield HomeScreen(runtime_context=runtime)
            with TabPane("Schedule", id="schedule"):
                yield ScheduleScreen()
            with TabPane("Guide", id="usage"):
                yield UsageScreen(runtime_context=runtime)
            with TabPane("Configuration", id="config"):
                yield ConfigScreen(runtime_context=runtime)
            with TabPane("About", id="about"):
                yield AboutScreen(runtime_context=runtime)

    def action_show_tab(self, tab: str) -> None:
        self.get_child_by_type(TabbedContent).active = tab

    def on_mount(self) -> None:
        runtime = get_runtime_context()
        self.title = "Outlook Mail Extractor"
        self.sub_title = "提取郵件內文"
        if not runtime.paths.config_file.exists():
            self.call_after_refresh(self._show_first_run_guidance)

    def _show_first_run_guidance(self) -> None:
        self.action_show_tab("about")
        self.notify(
            "尚未初始化設定，請到 About 分頁按「初始化設定」", severity="warning"
        )

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_confirm_quit(self) -> None:
        def handle_result(result: bool | None) -> None:
            if result:
                self.exit()

        self.push_screen(ConfirmScreen(), handle_result)


if __name__ == "__main__":
    app = OutlookMailExtractor()
    app.run()
