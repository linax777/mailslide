"""About tab screen."""

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Static

from ..config import get_last_migration_result, load_config
from ..config_migration import MigrationResult
from ..config_templates import all_configs_initialized, initialize_configs
from ..core import OutlookConnectionError
from ..i18n import resolve_language, set_language, t
from ..models import CheckStatus, ConfigStatus, OutlookStatus, SystemStatus
from ..runtime import RuntimeContext, get_runtime_context
from ..services.preflight import PreflightCheckService

if TYPE_CHECKING:
    from ..tui import OutlookMailExtractor


class AboutScreen(Container):
    """About 標籤頁 - 系統狀態檢查"""

    VERSION = "0.3.8"
    AUTHOR = "linax777"
    REPO_URL = "https://github.com/linax777/mailslide"
    BRAND_ASCII_ART = """
              _ _     _ _     _
    _ __ ___   __ _(_) |___| (_) __| | ___
   | '_ ` _ \\ / _` | | / __| | |/ _` |/ _ \\
   | | | | | | (_| | | \\__ \\ | | (_| |  __/
   |_| |_| |_|\\__,_|_|_|___/_|_|\\__,_|\\___|
 ============================================
     for Outlook Classic
"""

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        self._config_version: int | None = None
        self._migration_result: MigrationResult | None = None
        self._config_schema_summary = ""
        set_language(resolve_language(self._runtime.paths.config_file))

    def compose(self) -> ComposeResult:
        yield Static(t("ui.about.status.title"), id="status-title")
        yield Static("", id="status-content")
        with Horizontal():
            yield Button(t("ui.about.button.init"), id="init-config", variant="primary")
            yield Button(
                t("ui.about.button.refresh"), id="refresh-check", variant="default"
            )
            yield Button(
                t("ui.about.button.refresh_update"),
                id="refresh-update",
                variant="default",
            )
        yield Static("", id="update-status")
        yield Static("", id="about-info")

    def on_mount(self) -> None:
        about_info = self.query_one("#about-info", Static)
        about_info.styles.text_align = "center"
        about_info.styles.dock = "top"
        about_info.styles.height = "auto"
        self._update_init_button()
        self._show_about_info()
        self.refresh_update_status()
        self.refresh_config_schema_status()
        self.run_check()

    def _show_about_info(self) -> None:
        info = t(
            "ui.about.info",
            version=self.VERSION,
            author=self.AUTHOR,
            repo_url=self.REPO_URL,
        )
        schema_info = (
            f"\n\n{self._config_schema_summary}" if self._config_schema_summary else ""
        )
        self.query_one("#about-info", Static).update(
            f"\n\n\n{self.BRAND_ASCII_ART}\n{info}{schema_info}"
        )

    def _update_init_button(self) -> None:
        all_exist = self._check_all_configs_exist()
        btn = self.query_one("#init-config", Button)
        btn.disabled = all_exist

    def _check_all_configs_exist(self) -> bool:
        return all_configs_initialized(self._runtime.paths.config_dir)

    def _init_configs(self) -> tuple[int, int]:
        return initialize_configs(
            self._runtime.paths.config_dir,
            project_root=self._runtime.paths.project_root,
        )

    def run_check(self) -> None:
        status = self._perform_check()
        self._display_status(status)
        self.refresh_config_schema_status()

    def _perform_check(self) -> SystemStatus:
        config_status = self._check_config()
        outlook_status = self._check_outlook()
        return SystemStatus(config=config_status, outlook=outlook_status)

    def _check_config(self) -> ConfigStatus:
        config_path = self._runtime.paths.config_file
        if not config_path.exists():
            return ConfigStatus(
                status=CheckStatus.ERROR,
                message=t("ui.about.config.missing"),
            )

        try:
            config = load_config(config_path)
            version = config.get("config_version")
            self._config_version = version if isinstance(version, int) else None
            self._migration_result = get_last_migration_result()
            return ConfigStatus(status=CheckStatus.OK, message=t("ui.about.config.ok"))
        except Exception as e:
            self._config_version = None
            self._migration_result = None
            return ConfigStatus(
                status=CheckStatus.ERROR,
                message=t("ui.about.config.invalid", error=e),
            )

    def _check_outlook(self) -> OutlookStatus:
        try:
            config_path = self._runtime.paths.config_file
            config = load_config(config_path) if config_path.exists() else None
            preflight = PreflightCheckService(
                client_factory=self._runtime.client_factory,
            )
            result = preflight.run(config) if config else preflight.run({"jobs": []})

            if result.issues:
                issue_preview = "；".join(result.issues[:2])
                if len(result.issues) > 2:
                    issue_preview += t(
                        "ui.about.outlook.issue_more",
                        count=len(result.issues) - 2,
                    )
                return OutlookStatus(
                    status=CheckStatus.ERROR,
                    message=t("ui.about.outlook.issue_failed", issues=issue_preview),
                    account_count=result.account_count,
                )

            return OutlookStatus(
                status=CheckStatus.OK,
                message=t("ui.about.outlook.connected", count=result.account_count),
                account_count=result.account_count,
            )
        except OutlookConnectionError as e:
            return OutlookStatus(status=CheckStatus.ERROR, message=str(e))
        except Exception as e:
            return OutlookStatus(
                status=CheckStatus.ERROR,
                message=t("ui.about.outlook.connect_failed", error=e),
            )

    def _display_status(self, status: SystemStatus) -> None:
        lines = []
        config_icon = "✅" if status.config.status == CheckStatus.OK else "❌"
        outlook_icon = "✅" if status.outlook.status == CheckStatus.OK else "❌"

        lines.append(
            t(
                "ui.about.status.config",
                icon=config_icon,
                message=status.config.message,
            )
        )
        lines.append(
            t(
                "ui.about.status.outlook",
                icon=outlook_icon,
                message=status.outlook.message,
            )
        )

        status_content = self.query_one("#status-content", Static)
        status_content.update("\n".join(lines))

    def refresh_update_status(self) -> None:
        app = cast("OutlookMailExtractor", self.app)
        phase, result = app.get_update_check_state()

        if phase == "checking":
            text = t("ui.about.update.checking")
        elif phase == "available" and result and result.latest_version:
            text = t(
                "ui.about.update.available",
                latest=result.latest_version,
                command="uv tool upgrade mailslide",
            )
        elif phase == "up_to_date":
            text = t("ui.about.update.up_to_date")
        elif phase == "error" and result and result.error:
            text = t("ui.about.update.error", error=result.error)
        else:
            text = t("ui.about.update.pending")

        self.query_one("#update-status", Static).update(text)

    def refresh_config_schema_status(self) -> None:
        if not self._runtime.paths.config_file.exists():
            text = t("ui.about.config_schema.missing")
        elif self._config_version is None:
            text = t("ui.about.config_schema.unknown")
        else:
            text = t("ui.about.config_schema.version", version=self._config_version)
            if self._migration_result and self._migration_result.changed:
                backup = (
                    str(self._migration_result.backup_path)
                    if self._migration_result.backup_path
                    else "-"
                )
                text = (
                    f"{text}\n"
                    f"{t('ui.about.config_schema.migrated', from_version=self._migration_result.from_version, to_version=self._migration_result.to_version, backup=backup)}"
                )
            else:
                text = f"{text}\n{t('ui.about.config_schema.no_migration')}"
        self._config_schema_summary = text
        self._show_about_info()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "init-config":
            had_main_config = self._runtime.paths.config_file.exists()
            copied, skipped = self._init_configs()
            self._update_init_button()
            self.app.notify(
                t("ui.about.status.init_done", copied=copied, skipped=skipped),
                severity="information",
            )
            if not had_main_config and copied > 0:
                self.app.notify(t("ui.about.status.restart_hint"), severity="warning")
            self.run_check()
        elif event.button.id == "refresh-check":
            self.run_check()
        elif event.button.id == "refresh-update":
            app = cast("OutlookMailExtractor", self.app)
            app.trigger_update_check(manual=True)
