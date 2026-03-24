"""Outlook Mail Extractor - 應用程式入口"""

from pathlib import Path

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Middle
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    RadioButton,
    RadioSet,
    TabbedContent,
    TabPane,
)

from outlook_mail_extractor.i18n import get_language, resolve_language, set_language, t
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
                yield Label(f"{t('app.confirm_quit.message')}\n")
                with Horizontal():
                    yield Button(t("app.confirm_quit.yes"), variant="error", id="yes")
                    yield Button(t("app.confirm_quit.no"), variant="primary", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class LanguageScreen(ModalScreen[str | None]):
    def __init__(self, current_language: str):
        super().__init__()
        self._current_language = current_language

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield Label(f"{t('app.language.modal_title')}\n")
                with RadioSet(id="language-radio"):
                    yield RadioButton(
                        t("app.language.option.zh_tw"),
                        id="lang-zh",
                        value=self._current_language == "zh-TW",
                    )
                    yield RadioButton(
                        t("app.language.option.en_us"),
                        id="lang-en",
                        value=self._current_language == "en-US",
                    )
                with Horizontal():
                    yield Button(t("app.language.apply"), variant="primary", id="apply")
                    yield Button(
                        t("app.language.cancel"), variant="default", id="cancel"
                    )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "apply":
            selected = (
                "en-US" if self.query_one("#lang-en", RadioButton).value else "zh-TW"
            )
            self.dismiss(selected)


class OutlookMailExtractor(App):
    BINDINGS = [
        Binding("h", "show_tab('home')", "Home"),
        Binding("s", "show_tab('schedule')", "Schedule"),
        Binding("g", "show_tab('usage')", "Guide"),
        Binding("c", "show_tab('config')", "Config"),
        Binding("a", "show_tab('about')", "About"),
        Binding("l", "open_language_modal", "Language"),
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding(key="q", action="confirm_quit", description="Quit the app"),
    ]

    def compose(self) -> ComposeResult:
        runtime = get_runtime_context()
        set_language(resolve_language(runtime.paths.config_file))
        yield Header()
        yield Footer()
        with TabbedContent(initial="home"):
            with TabPane(t("app.tab.home"), id="home"):
                yield HomeScreen(runtime_context=runtime)
            with TabPane(t("app.tab.schedule"), id="schedule"):
                yield ScheduleScreen()
            with TabPane(t("app.tab.guide"), id="usage"):
                yield UsageScreen(runtime_context=runtime)
            with TabPane(t("app.tab.config"), id="config"):
                yield ConfigScreen(runtime_context=runtime)
            with TabPane(t("app.tab.about"), id="about"):
                yield AboutScreen(runtime_context=runtime)

    def action_show_tab(self, tab: str) -> None:
        self.get_child_by_type(TabbedContent).active = tab

    def on_mount(self) -> None:
        runtime = get_runtime_context()
        self.title = t("app.title")
        self.sub_title = t("app.subtitle")
        if not runtime.paths.config_file.exists():
            self.call_after_refresh(self._show_first_run_guidance)

    def _show_first_run_guidance(self) -> None:
        self.action_show_tab("about")
        self.notify(t("app.first_run.notice"), severity="warning")

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_confirm_quit(self) -> None:
        def handle_result(result: bool | None) -> None:
            if result:
                self.exit()

        self.push_screen(ConfirmScreen(), handle_result)

    def action_open_language_modal(self) -> None:
        self.push_screen(
            LanguageScreen(current_language=get_language()),
            self._handle_language_result,
        )

    def _handle_language_result(self, selected_language: str | None) -> None:
        if not selected_language:
            return

        current_language = get_language()
        if selected_language == current_language:
            self.notify(t("app.language.no_change"), severity="information")
            return

        runtime = get_runtime_context()
        try:
            self._save_ui_language(runtime.paths.config_file, selected_language)
        except Exception as e:
            self.notify(
                t("app.language.save_failed", error=e),
                severity="error",
            )
            return

        set_language(selected_language)
        active_tab = self.get_child_by_type(TabbedContent).active
        self.refresh(recompose=True)

        def restore_after_recompose() -> None:
            self.title = t("app.title")
            self.sub_title = t("app.subtitle")
            self.action_show_tab(active_tab)
            self.notify(t("app.language.changed", language=selected_language))

        self.call_after_refresh(restore_after_recompose)

    def _save_ui_language(self, config_path: Path, language: str) -> None:
        payload: dict[str, object]
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                raise ValueError("config/config.yaml 內容必須是 YAML 物件")
            payload = dict(loaded)
        else:
            payload = {"jobs": []}

        payload["ui_language"] = language
        config_path.parent.mkdir(parents=True, exist_ok=True)

        backup_path = config_path.with_suffix(".yaml.bak")
        if config_path.exists():
            backup_path.write_text(
                config_path.read_text(encoding="utf-8"), encoding="utf-8"
            )

        text = yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        temp_path = config_path.with_name(f".{config_path.name}.tmp")
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(config_path)


if __name__ == "__main__":
    app = OutlookMailExtractor()
    app.run()
