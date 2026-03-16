"""Outlook Mail Extractor - 應用程式入口"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from outlook_mail_extractor.screens import (
    AboutScreen,
    ConfigScreen,
    HomeScreen,
    ScheduleScreen,
)


class OutlookMailExtractor(App):
    BINDINGS = [
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding(key="q", action="quit", description="Quit the app"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent(initial="home"):
            with TabPane("Home", id="home"):
                yield HomeScreen()
            with TabPane("schedule", id="schedule"):
                yield ScheduleScreen()
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


if __name__ == "__main__":
    app = OutlookMailExtractor()
    app.run()
