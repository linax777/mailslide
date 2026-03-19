import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from outlook_mail_extractor.core import (
    EmailProcessor,
    OutlookClient,
    process_config_file,
)
from outlook_mail_extractor.models import EmailDTO
from outlook_mail_extractor.plugins import PluginCapability
from outlook_mail_extractor.logger import LogSessionManager
from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths


class DummyMessage:
    def __init__(self) -> None:
        self.move_calls = 0

    def Move(self, destination) -> None:  # noqa: N802
        self.move_calls += 1


class DummyPlugin:
    def __init__(
        self,
        name: str,
        prompt: str,
        execute_result: bool = True,
        move_message: bool = False,
        capabilities: set[PluginCapability] | None = None,
    ) -> None:
        self.name = name
        self._prompt = prompt
        self._execute_result = execute_result
        self._move_message = move_message
        self.config = SimpleNamespace(enabled=True)
        self.execute_calls = 0
        self.capabilities = capabilities or set()

    def build_effective_prompt(self) -> str:
        return self._prompt

    def supports(self, capability: PluginCapability) -> bool:
        return capability in self.capabilities

    def requires_llm(self) -> bool:
        return self.supports(PluginCapability.REQUIRES_LLM) or bool(self._prompt)

    def should_skip_by_response(self, llm_response: str):
        del llm_response
        return None

    async def execute(
        self, email_data: EmailDTO, llm_response: str, action_port
    ) -> bool:
        del email_data
        del llm_response
        self.execute_calls += 1
        if self._move_message:
            action_port.move_to_folder("plugin-folder")
        return self._execute_result


def _build_processor_with_stubbed_extract(stub_message: DummyMessage) -> EmailProcessor:
    class _FakeClient:
        def get_folder(
            self,
            account_name: str,
            folder_name: str,
            create_if_missing: bool = False,
        ) -> str:
            del account_name
            del create_if_missing
            return folder_name

    class _TestEmailProcessor(EmailProcessor):
        def extract_email_data(
            self,
            message,
            max_length: int | None = None,
        ) -> EmailDTO:
            del message
            del max_length
            return EmailDTO(
                subject="Test",
                sender="sender@example.com",
                received="now",
                body="hello",
                tables=[],
            )

    fake_client = cast(OutlookClient, _FakeClient())
    return _TestEmailProcessor(client=fake_client)


def test_no_llm_plugin_still_executes() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    plugin = DummyPlugin(name="write_file", prompt="")

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=None,
            plugins=[plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name=None,
            body_max_length=500,
        )
    )

    assert result.success is True
    assert plugin.execute_calls == 1
    assert message.move_calls == 0


def test_destination_move_works_without_llm_and_plugins() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=None,
            plugins=[],
            dry_run=False,
            no_move=False,
            destination_folder_name="destination-folder",
            body_max_length=500,
        )
    )

    assert result.success is True
    assert message.move_calls == 1


def test_move_to_folder_plugin_prevents_destination_double_move() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    plugin = DummyPlugin(
        name="move_to_folder",
        prompt="",
        move_message=True,
        capabilities={PluginCapability.MOVES_MESSAGE},
    )

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=None,
            plugins=[plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name="destination-folder",
            body_max_length=500,
        )
    )

    assert result.success is True
    assert plugin.execute_calls == 1
    assert message.move_calls == 1


def test_llm_required_plugin_reports_failure_when_llm_missing() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    no_llm_plugin = DummyPlugin(name="write_file", prompt="")
    llm_plugin = DummyPlugin(name="add_category", prompt="needs llm")

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=None,
            plugins=[no_llm_plugin, llm_plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name=None,
            body_max_length=500,
        )
    )

    assert no_llm_plugin.execute_calls == 1
    assert llm_plugin.execute_calls == 0
    assert result.success is False
    plugin_results = {item.plugin_name: item for item in result.plugin_results}
    assert plugin_results["add_category"].success is False
    assert "LLM client not available" in plugin_results["add_category"].message


def test_process_config_file_prefers_config_relative_llm_and_plugins(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "custom"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "llm-config.yaml").write_text("provider: openai\n", encoding="utf-8")
    (config_dir / "plugins").mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("jobs: []\n", encoding="utf-8")

    calls: dict[str, str | Path | None] = {"llm": None, "plugins": None}

    class FakeOutlookClient:
        def __init__(self) -> None:
            self._connected = False

        def connect(self) -> None:
            self._connected = True

        def disconnect(self) -> None:
            self._connected = False

        @property
        def is_connected(self) -> bool:
            return self._connected

    def fake_load_config(_path):
        return {"jobs": []}

    def fake_load_llm_config(path=None):
        calls["llm"] = path
        return SimpleNamespace(api_base="", model="")

    def fake_load_plugin_configs(path: Path):
        calls["plugins"] = path
        return {}

    runtime_context = RuntimeContext(
        paths=RuntimePaths(
            project_root=tmp_path,
            config_dir=config_dir,
            config_file=config_file,
            llm_config_file=tmp_path / "fallback" / "llm-config.yaml",
            plugins_dir=tmp_path / "fallback" / "plugins",
            logging_config_file=tmp_path / "config" / "logging.yaml",
            logs_dir=tmp_path / "logs",
            readme_file=tmp_path / "README.md",
        ),
        logger_manager=LogSessionManager(
            log_dir=tmp_path / "logs",
            log_config_path=tmp_path / "config" / "logging.yaml",
        ),
        client_factory=FakeOutlookClient,
    )

    asyncio.run(
        process_config_file(
            config_file=config_file,
            dry_run=True,
            no_move=True,
            runtime_context=runtime_context,
            config_loader=fake_load_config,
            llm_config_loader=fake_load_llm_config,
            plugin_config_loader=fake_load_plugin_configs,
        )
    )

    assert calls["llm"] == str(config_dir / "llm-config.yaml")
    assert calls["plugins"] == config_dir / "plugins"
