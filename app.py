"""Outlook Mail Extractor - 應用程式入口"""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabbedContent, TabPane

from outlook_mail_extractor.screens import ConfigScreen, HomeScreen


class OutlookMailExtractor(App):

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with TabbedContent(initial="home"):
            with TabPane("Home", id="home"):
                yield HomeScreen()
            with TabPane("Configuration", id="config"):
                yield ConfigScreen()

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
