"""Add-job modal screen."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, SelectionList, Static, Switch


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
        defaults: dict | None = None,
        title: str = "➕ 新增 Job",
        save_button_label: str = "儲存 Job",
    ):
        super().__init__()
        self._plugin_options = plugin_options
        self._defaults = defaults or {}
        self._title = title
        self._save_button_label = save_button_label

    def compose(self) -> ComposeResult:
        with Vertical(id="add-job-dialog"):
            yield Static(self._title, id="add-job-title")
            yield Static("工作名稱", classes="add-job-label")
            yield Input(self._default_text("name"), id="add-job-name")
            yield Static("啟用", classes="add-job-label")
            yield Switch(value=self._default_bool("enable", True), id="add-job-enable")
            yield Static("Outlook 帳號", classes="add-job-label")
            yield Input(self._default_text("account"), id="add-job-account")
            yield Static("來源資料夾", classes="add-job-label")
            yield Input(self._default_text("source"), id="add-job-source")
            yield Static("目標資料夾（可留空）", classes="add-job-label")
            yield Input(self._default_text("destination"), id="add-job-destination")
            yield Static("人工判斷資料夾（可留空）", classes="add-job-label")
            yield Input(
                self._default_text("manual_review_destination"),
                id="add-job-manual-review-destination",
            )
            yield Static("處理上限", classes="add-job-label")
            yield Input(str(self._default_limit()), id="add-job-limit")
            yield Static("Plugins（可多選）", classes="add-job-label")
            default_plugins = set(self._default_plugins())
            yield SelectionList(
                *[
                    (
                        option,
                        option,
                        option in default_plugins,
                    )
                    for option in self._plugin_options
                ],
                id="add-job-plugins",
            )
            yield Static("", id="add-job-error")
            with Horizontal(id="add-job-actions"):
                yield Button("取消", id="add-job-cancel")
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

    def _show_error(self, message: str) -> None:
        self.query_one("#add-job-error", Static).update(message)

    def _submit(self) -> None:
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
            self._show_error("name 為必填")
            return
        if not account:
            self._show_error("account 為必填")
            return
        if not source:
            self._show_error("source 為必填")
            return

        try:
            limit = int(limit_text)
            if limit <= 0:
                raise ValueError
        except ValueError:
            self._show_error("limit 必須是正整數")
            return

        selected_plugins = set(plugin_selector.selected)
        plugins = [
            option for option in self._plugin_options if option in selected_plugins
        ]

        if "move_to_folder" in plugins and destination:
            self._show_error("使用 move_to_folder 時，請不要設定 destination")
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

        self.dismiss(job)
