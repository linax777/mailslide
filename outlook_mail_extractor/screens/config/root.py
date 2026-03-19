"""Configuration root tab."""

from textual.app import ComposeResult
from textual.widgets import Static, TabbedContent, TabPane

from ...runtime import RuntimeContext, get_runtime_context
from .llm_tab import LLMConfigTab
from .main_tab import MainConfigTab
from .plugins_tab import PluginsConfigTab


class ConfigScreen(Static):
    """Configuration 標籤頁 - 設定檔檢視"""

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="main"):
            with TabPane("一般設定", id="main"):
                yield MainConfigTab(runtime_context=self._runtime)
            with TabPane("LLM 設定", id="llm"):
                yield LLMConfigTab(runtime_context=self._runtime)
            with TabPane("Plugin 設定", id="plugins"):
                yield PluginsConfigTab(runtime_context=self._runtime)
