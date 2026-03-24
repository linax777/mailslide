"""About tab screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Static

from ..config import load_config
from ..core import OutlookConnectionError
from ..i18n import resolve_language, set_language, t
from ..models import CheckStatus, ConfigStatus, OutlookStatus, SystemStatus
from ..runtime import RuntimeContext, get_runtime_context
from ..services.preflight import PreflightCheckService


class AboutScreen(Container):
    """About 標籤頁 - 系統狀態檢查"""

    SAMPLE_SUFFIX = ".yaml.sample"
    VERSION = "0.3.0"
    AUTHOR = "linax777"
    REPO_URL = "https://github.com/linax777/outlook-mail-extractor"

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()
        set_language(resolve_language(self._runtime.paths.config_file))

    def compose(self) -> ComposeResult:
        yield Static(t("ui.about.status.title"), id="status-title")
        yield Static("", id="status-content")
        with Horizontal():
            yield Button(t("ui.about.button.init"), id="init-config", variant="primary")
            yield Button(
                t("ui.about.button.refresh"), id="refresh-check", variant="default"
            )
        yield Static("", id="about-info")

    def on_mount(self) -> None:
        self._update_init_button()
        self._show_about_info()
        self.run_check()

    def _show_about_info(self) -> None:
        info = t(
            "ui.about.info",
            version=self.VERSION,
            author=self.AUTHOR,
            repo_url=self.REPO_URL,
        )
        self.query_one("#about-info", Static).update(info)

    def _update_init_button(self) -> None:
        all_exist = self._check_all_configs_exist()
        btn = self.query_one("#init-config", Button)
        btn.disabled = all_exist

    def _check_all_configs_exist(self) -> bool:
        config_dir = self._runtime.paths.config_dir
        if not config_dir.exists():
            return False
        sample_files = list(config_dir.rglob(f"*{self.SAMPLE_SUFFIX}"))
        for sample in sample_files:
            yaml_path = sample.with_suffix("")
            if not yaml_path.exists():
                return False
        return True

    def _init_configs(self) -> tuple[int, int]:
        copied = 0
        skipped = 0
        config_dir = self._runtime.paths.config_dir
        if not config_dir.exists():
            return (copied, skipped)
        sample_files = list(config_dir.rglob(f"*{self.SAMPLE_SUFFIX}"))
        for sample in sample_files:
            yaml_path = sample.with_suffix("")
            if yaml_path.exists():
                skipped += 1
            else:
                content = sample.read_text(encoding="utf-8")
                yaml_path.write_text(content, encoding="utf-8")
                copied += 1
        return (copied, skipped)

    def run_check(self) -> None:
        status = self._perform_check()
        self._display_status(status)

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
            load_config(config_path)
            return ConfigStatus(status=CheckStatus.OK, message=t("ui.about.config.ok"))
        except Exception as e:
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "init-config":
            copied, skipped = self._init_configs()
            self._update_init_button()
            status_content = self.query_one("#status-content", Static)
            status_content.update(
                t("ui.about.status.init_done", copied=copied, skipped=skipped)
            )
            self.run_check()
        elif event.button.id == "refresh-check":
            self.run_check()
