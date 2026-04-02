"""Add-job modal screen."""

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, SelectionList, Static, Switch

from ...i18n import t


class AddJobScreen(ModalScreen[dict | None]):
    """Modal screen for collecting a new job before writing config."""

    CSS = """
    AddJobScreen {
        align: center middle;
    }
    #add-job-dialog {
        width: 70;
        max-width: 90;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }
    #add-job-actions {
        height: auto;
        margin-top: 1;
    }
    #add-job-error {
        color: $error;
        min-height: 2;
    }
    #add-job-plugins {
        height: 7;
    }
    """

    def __init__(
        self,
        plugin_options: list[str],
        unavailable_plugins: list[str] | None = None,
        defaults: dict | None = None,
        title: str | None = None,
        save_button_label: str | None = None,
        save_attempt: Callable[[dict[str, object]], tuple[bool, str | None]]
        | None = None,
    ):
        super().__init__()
        self._plugin_options = plugin_options
        self._unavailable_plugin_keys = {
            plugin.casefold()
            for plugin in self._normalize_plugin_names(unavailable_plugins)
        }
        self._defaults = defaults or {}
        self._title = title or t("ui.add_job.title")
        self._save_button_label = save_button_label or t("ui.add_job.button.save")
        self._save_attempt = save_attempt
        self._is_saving = False

    def _normalize_plugin_names(self, plugins: list[str] | None) -> list[str]:
        if not isinstance(plugins, list):
            return []
        return [str(plugin).strip() for plugin in plugins if str(plugin).strip()]

    def _plugin_option_label(self, plugin_name: str) -> str:
        if plugin_name.casefold() not in self._unavailable_plugin_keys:
            return plugin_name
        return t("ui.add_job.field.plugin_unavailable", plugin=plugin_name)

    def compose(self) -> ComposeResult:
        with Vertical(id="add-job-dialog"):
            yield Static(self._title, id="add-job-title")
            yield Static(t("ui.add_job.field.name"), classes="add-job-label")
            yield Input(self._default_text("name"), id="add-job-name")
            yield Static(t("ui.add_job.field.enable"), classes="add-job-label")
            yield Switch(value=self._default_bool("enable", True), id="add-job-enable")
            yield Static(t("ui.add_job.field.account"), classes="add-job-label")
            yield Input(self._default_text("account"), id="add-job-account")
            yield Static(t("ui.add_job.field.source"), classes="add-job-label")
            yield Input(self._default_text("source"), id="add-job-source")
            yield Static(t("ui.add_job.field.destination"), classes="add-job-label")
            yield Input(self._default_text("destination"), id="add-job-destination")
            yield Static(
                t("ui.add_job.field.manual_review_destination"),
                classes="add-job-label",
            )
            yield Input(
                self._default_text("manual_review_destination"),
                id="add-job-manual-review-destination",
            )
            yield Static(t("ui.add_job.field.limit"), classes="add-job-label")
            yield Input(str(self._default_limit()), id="add-job-limit")
            yield Static(t("ui.add_job.field.plugins"), classes="add-job-label")
            default_plugins = set(self._default_plugins())
            yield SelectionList(
                *[
                    (
                        self._plugin_option_label(option),
                        option,
                        option in default_plugins,
                    )
                    for option in self._plugin_options
                ],
                id="add-job-plugins",
            )
            yield Static(
                t("ui.add_job.field.plugin_prompt_profiles"),
                classes="add-job-label",
            )
            default_profiles = self._default_plugin_prompt_profiles()
            for option in self._plugin_options:
                yield Static(
                    t("ui.add_job.field.plugin_profile_for", plugin=option),
                    classes="add-job-label",
                )
                yield Input(
                    default_profiles.get(option, ""),
                    id=self._plugin_profile_widget_id(option),
                )
            yield Static("", id="add-job-error")
            with Horizontal(id="add-job-actions"):
                yield Button(t("ui.add_job.button.cancel"), id="add-job-cancel")
                yield Button(
                    self._save_button_label,
                    id="add-job-save",
                    variant="primary",
                )

    def on_mount(self) -> None:
        self.query_one("#add-job-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-job-cancel":
            self.dismiss(None)
            return
        if event.button.id == "add-job-save":
            self._submit()

    def _default_text(self, key: str) -> str:
        value = self._defaults.get(key, "")
        return str(value) if value is not None else ""

    def _default_bool(self, key: str, fallback: bool) -> bool:
        value = self._defaults.get(key)
        return bool(value) if isinstance(value, bool) else fallback

    def _default_limit(self) -> int:
        value = self._defaults.get("limit", 10)
        if isinstance(value, int) and value > 0:
            return value
        return 10

    def _default_plugins(self) -> list[str]:
        plugins = self._defaults.get("plugins", [])
        if isinstance(plugins, list):
            return [str(plugin).strip() for plugin in plugins if str(plugin).strip()]
        return []

    def _default_plugin_prompt_profiles(self) -> dict[str, str]:
        raw = self._defaults.get("plugin_prompt_profiles", {})
        if not isinstance(raw, dict):
            return {}

        profiles: dict[str, str] = {}
        for plugin, profile in raw.items():
            plugin_name = str(plugin).strip()
            profile_key = str(profile).strip()
            if plugin_name and profile_key:
                profiles[plugin_name] = profile_key
        return profiles

    def _plugin_profile_widget_id(self, plugin_name: str) -> str:
        return f"add-job-plugin-profile-{plugin_name}"

    def _collect_plugin_prompt_profiles(
        self,
        selected_plugins: list[str],
    ) -> dict[str, str]:
        profiles: dict[str, str] = {}
        for plugin in selected_plugins:
            profile_key = self.query_one(
                f"#{self._plugin_profile_widget_id(plugin)}", Input
            ).value.strip()
            if profile_key:
                profiles[plugin] = profile_key
        return profiles

    def _show_error(self, message: str) -> None:
        self.query_one("#add-job-error", Static).update(message)

    def _set_saving_state(self, is_saving: bool) -> None:
        self._is_saving = is_saving
        save_button = self.query_one("#add-job-save", Button)
        save_button.disabled = is_saving

    def _submit(self) -> None:
        if self._is_saving:
            return

        name = self.query_one("#add-job-name", Input).value.strip()
        account = self.query_one("#add-job-account", Input).value.strip()
        source = self.query_one("#add-job-source", Input).value.strip()
        destination = self.query_one("#add-job-destination", Input).value.strip()
        manual_review_destination = self.query_one(
            "#add-job-manual-review-destination", Input
        ).value.strip()
        limit_text = self.query_one("#add-job-limit", Input).value.strip()
        plugin_selector = self.query_one("#add-job-plugins", SelectionList)
        enable = self.query_one("#add-job-enable", Switch).value

        if not name:
            self._show_error(t("ui.add_job.error.name_required"))
            return
        if not account:
            self._show_error(t("ui.add_job.error.account_required"))
            return
        if not source:
            self._show_error(t("ui.add_job.error.source_required"))
            return

        try:
            limit = int(limit_text)
            if limit <= 0:
                raise ValueError
        except ValueError:
            self._show_error(t("ui.add_job.error.limit_positive"))
            return

        selected_plugins = set(plugin_selector.selected)
        plugins = [
            option for option in self._plugin_options if option in selected_plugins
        ]
        plugin_prompt_profiles = self._collect_plugin_prompt_profiles(plugins)

        if "move_to_folder" in plugins and destination:
            self._show_error(t("ui.add_job.error.destination_conflict"))
            return

        job: dict[str, object] = {
            "name": name,
            "enable": enable,
            "account": account,
            "source": source,
            "limit": limit,
            "plugins": plugins,
        }
        if destination:
            job["destination"] = destination
        if manual_review_destination:
            job["manual_review_destination"] = manual_review_destination
        if plugin_prompt_profiles:
            job["plugin_prompt_profiles"] = plugin_prompt_profiles

        if self._save_attempt is None:
            self.dismiss(job)
            return

        self._set_saving_state(True)
        error_message: str | None = None
        try:
            saved, error_message = self._save_attempt(job)
        except Exception as e:
            saved = False
            error_message = str(e)

        if saved:
            self.dismiss(None)
            return

        self._set_saving_state(False)
        self._show_error(error_message or t("ui.add_job.error.save_failed"))
