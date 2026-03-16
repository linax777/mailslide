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
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding(key="q", action="confirm_quit", description="Quit the app"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent(initial="home"):
            with TabPane("Home", id="home"):
                yield HomeScreen()
            with TabPane("schedule", id="schedule"):
                yield ScheduleScreen()
            with TabPane("Usage", id="usage"):
                yield UsageScreen()
            with TabPane("Configuration", id="config"):
                yield ConfigScreen()
            with TabPane("About", id="about"):
                yield AboutScreen()

    def action_show_tab(self, tab: str) -> None:
        self.get_child_by_type(TabbedContent).active = tab

    def on_mount(self) -> None:
        self.title = "Outlook Mail Extractor"
        self.sub_title = "提取郵件內文"

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
