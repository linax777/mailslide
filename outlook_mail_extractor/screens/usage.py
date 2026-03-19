"""Usage tab screen."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import MarkdownViewer, Static

from ..runtime import RuntimeContext, get_runtime_context


class UsageScreen(Static):
    """使用說明分頁"""

    def __init__(self, runtime_context: RuntimeContext | None = None):
        super().__init__()
        self._runtime = runtime_context or get_runtime_context()

    def compose(self) -> ComposeResult:
        content = self._get_usage_content()
        with VerticalScroll():
            yield MarkdownViewer(content)

    def _get_usage_content(self) -> str:
        readme_path = self._runtime.paths.readme_file
        if readme_path.exists():
            return readme_path.read_text(encoding="utf-8")
        return "# 使用說明\n\n請參考 README.md"
