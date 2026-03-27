"""Textual TUI application entry point."""

import asyncio
from pathlib import Path

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Horizontal, Middle, Vertical
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
from textual.worker import Worker

from . import __version__
from .i18n import get_language, resolve_language, set_language, t
from .runtime import get_runtime_context
from .screens import (
    AboutScreen,
    ConfigScreen,
    HomeScreen,
    ScheduleScreen,
    UsageScreen,
)
from .services.update_check import UpdateCheckResult, UpdateCheckService


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmScreen {
        layers: base dialog;
    }

    #confirm-overlay {
        layer: dialog;
        position: absolute;
        dock: top;
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #confirm-dialog {
        width: auto;
        height: auto;
        padding: 1 2;
    }

    #confirm-message {
        text-align: center;
    }

    #confirm-actions {
        width: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="confirm-overlay"):
            with Vertical(id="confirm-dialog"):
                yield Label(
                    f"\n\n\n\n\n\n{t('app.confirm_quit.message')}\n",
                    id="confirm-message",
                )
                with Horizontal(id="confirm-actions"):
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
    UPDATE_CHECK_DELAY_SECONDS = 20

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

    def __init__(self):
        super().__init__()
        self._update_service = UpdateCheckService(current_version=__version__)
        self._update_worker: Worker | None = None
        self._update_check_phase = "idle"
        self._update_check_result: UpdateCheckResult | None = None
        self._update_notified = False

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
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            self.run_worker(self._delayed_update_check(), exclusive=False)

    def _show_first_run_guidance(self) -> None:
        self.action_show_tab("about")
        self.notify(t("app.first_run.notice"), severity="warning")

    def trigger_update_check(self, manual: bool = False) -> None:
        if self._update_worker and self._update_worker.is_running:
            if manual:
                self.notify(t("app.update.notify.checking"), severity="information")
            return

        self._update_worker = self.run_worker(
            self._execute_update_check(manual=manual),
            exclusive=True,
        )

    def get_update_check_state(self) -> tuple[str, UpdateCheckResult | None]:
        return self._update_check_phase, self._update_check_result

    async def _delayed_update_check(self) -> None:
        await asyncio.sleep(self.UPDATE_CHECK_DELAY_SECONDS)
        self.trigger_update_check(manual=False)

    async def _execute_update_check(self, manual: bool) -> None:
        self._update_check_phase = "checking"
        self._publish_update_check_state()

        try:
            result = await asyncio.to_thread(self._update_service.check)
            self._update_check_result = result

            if result.error:
                self._update_check_phase = "error"
                if manual:
                    self.notify(
                        t("app.update.notify.failed", error=result.error),
                        severity="warning",
                    )
                return

            if result.has_update:
                self._update_check_phase = "available"
                if manual or not self._update_notified:
                    self.notify(
                        t(
                            "app.update.notify.available",
                            current=result.current_version,
                            latest=result.latest_version,
                            command="uv tool upgrade mailslide",
                        ),
                        severity="warning",
                    )
                    self._update_notified = True
                return

            self._update_check_phase = "up_to_date"
            if manual:
                self.notify(t("app.update.notify.up_to_date"), severity="information")
        finally:
            self._publish_update_check_state()
            self._update_worker = None

    def _publish_update_check_state(self) -> None:
        try:
            about = self.query_one(AboutScreen)
            about.refresh_update_status()
        except Exception:
            pass

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


def main() -> int:
    app = OutlookMailExtractor()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
