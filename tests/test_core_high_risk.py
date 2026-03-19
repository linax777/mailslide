import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from outlook_mail_extractor.core import (
    EmailProcessor,
    OutlookClient,
    process_config_file,
)


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
    ) -> None:
        self.name = name
        self._prompt = prompt
        self._execute_result = execute_result
        self._move_message = move_message
        self.config = SimpleNamespace(enabled=True)
        self.execute_calls = 0

    def build_effective_prompt(self) -> str:
        return self._prompt

    async def execute(
        self, email_data: dict, llm_response: str, outlook_client
    ) -> bool:
        self.execute_calls += 1
        if self._move_message:
            email_data["_message"].Move("plugin-folder")
        return self._execute_result


def _build_processor_with_stubbed_extract(stub_message: DummyMessage) -> EmailProcessor:
    class _TestEmailProcessor(EmailProcessor):
        def extract_email_data(self, message, max_length: int | None = None) -> dict:
            del message
            del max_length
            return {
                "subject": "Test",
                "sender": "sender@example.com",
                "received": "now",
                "body": "hello",
                "tables": [],
                "_message": stub_message,
                "_account": None,
            }

    fake_client = cast(OutlookClient, object())
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
            dst_folder=None,
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
            dst_folder="destination-folder",
            body_max_length=500,
        )
    )

    assert result.success is True
    assert message.move_calls == 1


def test_move_to_folder_plugin_prevents_destination_double_move() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    plugin = DummyPlugin(name="move_to_folder", prompt="", move_message=True)

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=None,
            plugins=[plugin],
            dry_run=False,
            no_move=False,
            dst_folder="destination-folder",
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
            dst_folder=None,
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
    monkeypatch, tmp_path: Path
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

    def fake_load_plugin_configs(path="config/plugins"):
        calls["plugins"] = path
        return {}

    monkeypatch.setattr("outlook_mail_extractor.core.OutlookClient", FakeOutlookClient)
    monkeypatch.setattr(
        "outlook_mail_extractor.core.load_llm_config", fake_load_llm_config
    )
    monkeypatch.setattr(
        "outlook_mail_extractor.core.load_plugin_configs", fake_load_plugin_configs
    )
    monkeypatch.setattr("outlook_mail_extractor.config.load_config", fake_load_config)

    asyncio.run(
        process_config_file(config_file=config_file, dry_run=True, no_move=True)
    )

    assert calls["llm"] == str(config_dir / "llm-config.yaml")
    assert calls["plugins"] == config_dir / "plugins"
