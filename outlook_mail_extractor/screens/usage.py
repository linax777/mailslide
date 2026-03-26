"""Usage tab screen."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import MarkdownViewer, Static

from ..i18n import get_language, t
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
        for readme_path in self._resolve_readme_candidates(get_language()):
            if readme_path.exists():
                return readme_path.read_text(encoding="utf-8")
        return t("ui.usage.fallback")

    def _resolve_readme_candidates(self, language: str) -> tuple[Path, ...]:
        root = self._runtime.paths.project_root
        default_readme = self._runtime.paths.readme_file
        if language == "en-US":
            return (root / "GUIDE.en.md", root / "README.en.md", default_readme)
        return (root / "GUIDE.md", default_readme)
