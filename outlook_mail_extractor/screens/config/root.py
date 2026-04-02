"""Configuration root tab."""

from textual.app import ComposeResult
from textual.widgets import Static, TabbedContent, TabPane

from ...i18n import t
from ...runtime import RuntimeContext, get_runtime_context
from .llm_tab import LLMConfigTab
from .main_tab import MainConfigTab
from .plugins_tab import PluginsConfigTab


class ConfigScreen(Static):
    """Configuration 標籤頁 - 設定檔檢視"""

    CSS = """
    ConfigScreen TabbedContent > ContentTabs > Tab:focus {
        background: $accent 30%;
        color: $text;
        text-style: bold;
    }
    ConfigScreen TabbedContent > ContentTabs > Tab.-active {
        background: $accent 20%;
        color: $text;
        text-style: bold;
    }
    """

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="main"):
            with TabPane(t("ui.config.tab.main"), id="main"):
                yield MainConfigTab(runtime_context=self._runtime)
            with TabPane(t("ui.config.tab.llm"), id="llm"):
                yield LLMConfigTab(runtime_context=self._runtime)
            with TabPane(t("ui.config.tab.plugins"), id="plugins"):
                yield PluginsConfigTab(runtime_context=self._runtime)
