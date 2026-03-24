"""About tab screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Static

from ..config import load_config
from ..core import OutlookConnectionError
from ..models import CheckStatus, ConfigStatus, OutlookStatus, SystemStatus
from ..runtime import RuntimeContext, get_runtime_context
from ..services.preflight import PreflightCheckService


class AboutScreen(Container):
    """About 標籤頁 - 系統狀態檢查"""

    SAMPLE_SUFFIX = ".yaml.sample"
    VERSION = "0.2.7"
    AUTHOR = "linax777"
    REPO_URL = "https://github.com/linax777/outlook-mail-extractor"

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()

    def compose(self) -> ComposeResult:
        yield Static("🔧 系統狀態", id="status-title")
        yield Static("", id="status-content")
        with Horizontal():
            yield Button("初始化設定", id="init-config", variant="primary")
            yield Button("重新檢查", id="refresh-check", variant="default")
        yield Static("", id="about-info")

    def on_mount(self) -> None:
        self._update_init_button()
        self._show_about_info()
        self.run_check()

    def _show_about_info(self) -> None:
        info = f"""📦 版本: {self.VERSION}
👤 作者: {self.AUTHOR}
🔗 GitHub: {self.REPO_URL}
📜 授權: MIT License

一款使用 Python + Textual 開發的 Outlook 郵件提取工具。"""
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
                message="找不到 config.yaml，請參考 config/config.yaml.sample 建立",
            )

        try:
            load_config(config_path)
            return ConfigStatus(status=CheckStatus.OK, message="正常")
        except Exception as e:
            return ConfigStatus(status=CheckStatus.ERROR, message=f"格式錯誤 - {e}")

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
                    issue_preview += f"；另有 {len(result.issues) - 2} 個 jobs 設定有誤"
                return OutlookStatus(
                    status=CheckStatus.ERROR,
                    message=f"設定檢查失敗 - {issue_preview}",
                    account_count=result.account_count,
                )

            return OutlookStatus(
                status=CheckStatus.OK,
                message=f"已連線 ({result.account_count} 個帳號)",
                account_count=result.account_count,
            )
        except OutlookConnectionError as e:
            return OutlookStatus(status=CheckStatus.ERROR, message=str(e))
        except Exception as e:
            return OutlookStatus(status=CheckStatus.ERROR, message=f"連線失敗 - {e}")

    def _display_status(self, status: SystemStatus) -> None:
        lines = []
        config_icon = "✅" if status.config.status == CheckStatus.OK else "❌"
        outlook_icon = "✅" if status.outlook.status == CheckStatus.OK else "❌"

        lines.append(f"{config_icon} 設定檔: {status.config.message}")
        lines.append(f"{outlook_icon} Outlook: {status.outlook.message}")

        status_content = self.query_one("#status-content", Static)
        status_content.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "init-config":
            copied, skipped = self._init_configs()
            self._update_init_button()
            status_content = self.query_one("#status-content", Static)
            status_content.update(f"已初始化設定檔 (新增: {copied}, 跳過: {skipped})")
            self.run_check()
        elif event.button.id == "refresh-check":
            self.run_check()
