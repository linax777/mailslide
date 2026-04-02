from pathlib import Path
from typing import Any

from outlook_mail_extractor.i18n import set_language
from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths
from outlook_mail_extractor.screens.usage import UsageScreen


class _FakeLoggerManager:
    def set_ui_sink(self, callback: Any) -> None:
        del callback

    def start_session(self, enable_ui_sink: bool = False) -> Path:
        del enable_ui_sink
        return Path("logs/session.log")

    def get_current_log_path(self) -> Path | None:
        return None

    def get_display_level(self) -> str:
        return "INFO"

    def set_display_level(self, level: str) -> None:
        del level


def _runtime_context(tmp_path: Path) -> RuntimeContext:
    config_dir = tmp_path / "config"
    paths = RuntimePaths(
        project_root=tmp_path,
        config_dir=config_dir,
        config_file=config_dir / "config.yaml",
        llm_config_file=config_dir / "llm-config.yaml",
        plugins_dir=config_dir / "plugins",
        logging_config_file=config_dir / "logging.yaml",
        logs_dir=tmp_path / "logs",
        readme_file=tmp_path / "README.md",
    )
    return RuntimeContext(
        paths=paths,
        logger_manager=_FakeLoggerManager(),
        client_factory=lambda: None,
    )


def test_usage_prefers_english_guide_for_en_us(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.readme_file.write_text("en readme", encoding="utf-8")
    (tmp_path / "GUIDE.en.md").write_text("en guide", encoding="utf-8")
    set_language("en-US")

    screen = UsageScreen(runtime_context=runtime)

    assert screen._get_usage_content() == "en guide"


def test_usage_falls_back_to_default_readme_when_english_guide_missing(
    tmp_path: Path,
) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.readme_file.write_text("en readme", encoding="utf-8")
    set_language("en-US")

    screen = UsageScreen(runtime_context=runtime)

    assert screen._get_usage_content() == "en readme"


def test_usage_falls_back_to_legacy_english_readme_when_default_readme_missing(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    paths = RuntimePaths(
        project_root=tmp_path,
        config_dir=config_dir,
        config_file=config_dir / "config.yaml",
        llm_config_file=config_dir / "llm-config.yaml",
        plugins_dir=config_dir / "plugins",
        logging_config_file=config_dir / "logging.yaml",
        logs_dir=tmp_path / "logs",
        readme_file=tmp_path / "MISSING.md",
    )
    runtime = RuntimeContext(
        paths=paths,
        logger_manager=_FakeLoggerManager(),
        client_factory=lambda: None,
    )
    (tmp_path / "README.en.md").write_text("legacy en readme", encoding="utf-8")
    set_language("en-US")

    screen = UsageScreen(runtime_context=runtime)

    assert screen._get_usage_content() == "legacy en readme"


def test_usage_prefers_guide_for_non_en_locale(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.readme_file.write_text("en readme", encoding="utf-8")
    (tmp_path / "README.zh-TW.md").write_text("zh readme", encoding="utf-8")
    (tmp_path / "GUIDE.md").write_text("zh guide", encoding="utf-8")
    set_language("zh-TW")

    screen = UsageScreen(runtime_context=runtime)

    assert screen._get_usage_content() == "zh guide"


def test_usage_zh_tw_falls_back_to_traditional_chinese_readme(tmp_path: Path) -> None:
    runtime = _runtime_context(tmp_path)
    runtime.paths.readme_file.write_text("en readme", encoding="utf-8")
    (tmp_path / "README.zh-TW.md").write_text("zh readme", encoding="utf-8")
    set_language("zh-TW")

    screen = UsageScreen(runtime_context=runtime)

    assert screen._get_usage_content() == "zh readme"


def test_usage_reads_packaged_english_guide_when_local_docs_missing(
    tmp_path: Path,
) -> None:
    runtime = _runtime_context(tmp_path)
    set_language("en-US")

    screen = UsageScreen(runtime_context=runtime)

    content = screen._get_usage_content()

    assert "Extract, analyze, and automate Outlook emails on Windows" in content
    assert "Current workflow notes" in content
    assert "Configuration -> General -> Reload" in content


def test_usage_reads_packaged_zh_tw_guide_when_local_docs_missing(
    tmp_path: Path,
) -> None:
    runtime = _runtime_context(tmp_path)
    set_language("zh-TW")

    screen = UsageScreen(runtime_context=runtime)

    content = screen._get_usage_content()

    assert "從 Outlook 提取郵件工具" in content
    assert "近期流程說明" in content
    assert "重新載入" in content


def test_packaged_guides_match_root_guides() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    assert (repo_root / "GUIDE.en.md").read_text(encoding="utf-8") == (
        repo_root / "outlook_mail_extractor" / "resources" / "docs" / "GUIDE.en.md"
    ).read_text(encoding="utf-8")
    assert (repo_root / "GUIDE.md").read_text(encoding="utf-8") == (
        repo_root / "outlook_mail_extractor" / "resources" / "docs" / "GUIDE.md"
    ).read_text(encoding="utf-8")
