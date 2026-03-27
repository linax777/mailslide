"""Usage tab screen."""

from importlib import resources
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

        for resource_name in self._resolve_packaged_guide_candidates(get_language()):
            content = self._read_packaged_doc_text(resource_name)
            if content is not None:
                return content

        return t("ui.usage.fallback")

    def _resolve_readme_candidates(self, language: str) -> tuple[Path, ...]:
        root = self._runtime.paths.project_root
        default_readme = self._runtime.paths.readme_file
        if language == "en-US":
            return (
                root / "GUIDE.en.md",
                default_readme,
                root / "README.en.md",
            )
        return (root / "GUIDE.md", root / "README.zh-TW.md", default_readme)

    def _resolve_packaged_guide_candidates(self, language: str) -> tuple[str, ...]:
        if language == "en-US":
            return ("GUIDE.en.md", "GUIDE.md")
        return ("GUIDE.md", "GUIDE.en.md")

    def _read_packaged_doc_text(self, filename: str) -> str | None:
        try:
            docs_root = resources.files("outlook_mail_extractor").joinpath(
                "resources", "docs"
            )
            resource = docs_root.joinpath(filename)
            if not resource.is_file():
                return None
            return resource.read_text(encoding="utf-8")
        except (FileNotFoundError, ModuleNotFoundError):
            return None
