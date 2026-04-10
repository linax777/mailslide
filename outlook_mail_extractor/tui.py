"""Textual TUI application entry point."""

import asyncio
from pathlib import Path
from typing import Protocol, cast

import yaml

from mailslide.config_models import AppConfig, ConfigValidationError
from mailslide.config_repository import ConfigRepository
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container, Horizontal, Middle, Vertical
from textual.screen import ModalScreen
from textual.widgets._footer import FooterKey
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
from .screens.config.io_helpers import write_yaml_with_backup
from .screens import (
    AboutScreen,
    ConfigScreen,
    HomeScreen,
    ScheduleScreen,
    UsageScreen,
)
from .services.update_check import UpdateCheckResult, UpdateCheckService
from .terminal_title import resolve_terminal_title, set_terminal_title


class ContextualFooter(Footer):
    """Footer that filters visible bindings by active context."""

    def compose(self) -> ComposeResult:
        if not self._bindings_ready:
            return
        app = cast("_FooterActionProvider", self.app)
        visible_actions = app.get_footer_visible_actions()
        bindings = self.screen.active_bindings
        for _, binding, enabled, tooltip in bindings.values():
            if not binding.show or binding.action not in visible_actions:
                continue
            yield FooterKey(
                binding.key,
                self.app.get_key_display(binding),
                binding.description,
                binding.action,
                disabled=not enabled,
                tooltip=tooltip,
            ).data_bind(compact=self.compact)


class _FooterActionProvider(Protocol):
    def get_footer_visible_actions(self) -> set[str]: ...


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
        self._last_top_tab = "home"
        self._last_config_tab = "main"

    def compose(self) -> ComposeResult:
        runtime = get_runtime_context()
        set_language(resolve_language(runtime.paths.config_file))
        yield Header()
        yield ContextualFooter()
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
        self._last_top_tab = tab
        self.get_child_by_type(TabbedContent).active = tab
        self._refresh_footer()

    def _refresh_footer(self) -> None:
        try:
            footer = self.query_one(ContextualFooter)
        except Exception:
            return
        if not hasattr(footer, "call_after_refresh") or not hasattr(
            footer, "recompose"
        ):
            return
        footer.call_after_refresh(footer.recompose)

    def _resolve_footer_context(self) -> str:
        try:
            screen_name = type(self.screen).__name__
        except Exception:
            screen_name = ""
        if screen_name == "PluginConfigEditorModal":
            return "modal.plugin_editor"
        if screen_name == "LanguageScreen":
            return "modal.language"
        if screen_name == "ConfirmScreen":
            return "modal.confirm_quit"

        active_top_tab = self._last_top_tab
        try:
            active_top_tab = self.get_child_by_type(TabbedContent).active
        except Exception:
            pass
        else:
            self._last_top_tab = active_top_tab

        if active_top_tab != "config":
            return active_top_tab

        active_config_tab = self._last_config_tab
        try:
            config_tabbed = self.query_one(ConfigScreen).query_one(TabbedContent)
            active_config_tab = config_tabbed.active
        except Exception:
            pass
        else:
            self._last_config_tab = active_config_tab

        return f"config.{active_config_tab}"

    def get_footer_visible_actions(self) -> set[str]:
        context = self._resolve_footer_context()
        global_actions = {
            "open_language_modal",
            "toggle_dark",
            "confirm_quit",
        }
        context_actions = {
            "home": {"show_tab('schedule')", "show_tab('config')", "show_tab('about')"},
            "schedule": {"show_tab('home')", "show_tab('config')", "show_tab('about')"},
            "usage": {"show_tab('home')", "show_tab('config')", "show_tab('about')"},
            "about": {"show_tab('home')", "show_tab('config')"},
            "config.main": {
                "show_tab('home')",
                "show_tab('schedule')",
                "show_tab('about')",
            },
            "config.llm": {
                "show_tab('home')",
                "show_tab('schedule')",
                "show_tab('about')",
            },
            "config.plugins": {
                "show_tab('home')",
                "show_tab('schedule')",
                "show_tab('about')",
            },
            "modal.plugin_editor": set(),
            "modal.language": set(),
            "modal.confirm_quit": set(),
        }
        return global_actions | context_actions.get(context, set())

    def _request_home_auto_refresh(self) -> None:
        try:
            self.query_one(HomeScreen).request_auto_refresh_on_entry()
        except Exception:
            pass

    def on_tabbed_content_tab_activated(
        self,
        event: TabbedContent.TabActivated,
    ) -> None:
        pane_id = event.pane.id
        if pane_id in {"home", "schedule", "usage", "config", "about"}:
            self._last_top_tab = pane_id
        if pane_id in {"main", "llm", "plugins"}:
            self._last_config_tab = pane_id

        self._refresh_footer()
        if pane_id != "home":
            return
        self._request_home_auto_refresh()

    def on_screen_resume(self) -> None:
        self._refresh_footer()

    def on_mount(self) -> None:
        runtime = get_runtime_context()
        set_terminal_title(resolve_terminal_title(runtime.paths.config_file))
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
        repository = ConfigRepository(config_path)
        config = AppConfig(jobs=[])
        if config_path.exists():
            raw_payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw_payload, dict):
                raise ValueError("YAML 物件")
            try:
                config = repository.load()
            except (ConfigValidationError, ValueError):
                raw_payload["ui_language"] = language
                write_yaml_with_backup(
                    config_path,
                    raw_payload,
                    backup_path=config_path.with_suffix(".yaml.bak"),
                )
                return
        config.ui_language = language
        repository.save(config)


def main() -> int:
    app = OutlookMailExtractor()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
