import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from outlook_mail_extractor.core import (
    EmailProcessor,
    OutlookClient,
    process_config_file,
)
from outlook_mail_extractor.models import EmailAnalysisResult, EmailDTO
from outlook_mail_extractor.models import PluginExecutionResult, PluginExecutionStatus
from outlook_mail_extractor.plugins import PluginCapability
from outlook_mail_extractor.logger import LogSessionManager
from outlook_mail_extractor.runtime import RuntimeContext, RuntimePaths


class DummyMessage:
    def __init__(self) -> None:
        self.move_calls = 0
        self.move_destinations: list[str] = []

    def Move(self, destination) -> None:  # noqa: N802
        self.move_calls += 1
        self.move_destinations.append(str(destination))


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


class ActionAwarePlugin:
    def __init__(
        self,
        name: str,
        prompt: str,
        expected_action: str,
        move_message: bool = False,
        capabilities: set[PluginCapability] | None = None,
    ) -> None:
        self.name = name
        self._prompt = prompt
        self._expected_action = expected_action
        self._move_message = move_message
        self.config = SimpleNamespace(enabled=True)
        self.execute_calls = 0
        self.capabilities = capabilities or {PluginCapability.REQUIRES_LLM}

    def build_effective_prompt(self) -> str:
        return self._prompt

    def supports(self, capability: PluginCapability) -> bool:
        return capability in self.capabilities

    def requires_llm(self) -> bool:
        return self.supports(PluginCapability.REQUIRES_LLM)

    def should_skip_by_response(self, llm_response: str):
        del llm_response
        return None

    async def execute(
        self,
        email_data: EmailDTO,
        llm_response: str,
        action_port,
    ) -> PluginExecutionResult:
        del email_data
        self.execute_calls += 1
        response_data = json.loads(llm_response)
        if response_data.get("action") != self._expected_action:
            return PluginExecutionResult(
                status=PluginExecutionStatus.SKIPPED,
                code="action_mismatch",
                message="Action mismatch",
            )
        if self._move_message:
            action_port.move_to_folder("plugin-folder")
        return PluginExecutionResult(
            status=PluginExecutionStatus.SUCCESS,
            message="ok",
        )


class FakeLLMClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        del user_prompt
        self.calls.append(system_prompt)
        if "APPOINTMENT_ONLY" in system_prompt:
            return '{"action":"appointment","create":true}'
        if "MOVE_ONLY" in system_prompt:
            return '{"action":"move","folder":"會議"}'
        return '{"action":"appointment","create":true}'


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


def test_process_job_cancellation_stops_before_next_message() -> None:
    class _FakeItems:
        def __init__(self, messages) -> None:
            self._messages = messages
            self._index = -1

        def Sort(self, _field: str, _descending: bool) -> None:  # noqa: N802
            return None

        def GetFirst(self):  # noqa: N802
            self._index = 0
            if self._index >= len(self._messages):
                return None
            return self._messages[self._index]

        def GetNext(self):  # noqa: N802
            self._index += 1
            if self._index >= len(self._messages):
                return None
            return self._messages[self._index]

    class _FakeFolder:
        def __init__(self, messages) -> None:
            self.Items = _FakeItems(messages)  # noqa: N815

    class _FakeClient:
        def get_folder(
            self,
            account: str,
            folder_path: str,
            create_if_missing: bool = False,
        ):
            del account
            del folder_path
            del create_if_missing
            return _FakeFolder([SimpleNamespace(Class=43), SimpleNamespace(Class=43)])

    class _CountingEmailProcessor(EmailProcessor):
        def __init__(self) -> None:
            super().__init__(client=cast(OutlookClient, _FakeClient()))
            self.processed_count = 0

        async def _process_email(
            self,
            message,
            account_name: str,
            llm_client,
            plugins,
            dry_run: bool,
            no_move: bool,
            destination_folder_name: str | None = None,
            manual_review_destination_folder_name: str | None = None,
            body_max_length: int | None = None,
            llm_mode: str = "per_plugin",
            cancel_requested=None,
        ) -> EmailAnalysisResult:
            del message
            del account_name
            del llm_client
            del plugins
            del dry_run
            del no_move
            del destination_folder_name
            del manual_review_destination_folder_name
            del body_max_length
            del llm_mode
            del cancel_requested
            self.processed_count += 1
            return EmailAnalysisResult(
                email_subject="mail",
                llm_response="",
                plugin_results=[],
                success=True,
                metrics={},
            )

    processor = _CountingEmailProcessor()
    call_count = {"count": 0}

    def cancel_requested() -> bool:
        call_count["count"] += 1
        return call_count["count"] >= 2

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            processor.process_job(
                job_config={
                    "name": "cancel-test",
                    "account": "acc",
                    "source": "Inbox",
                    "plugins": [],
                },
                cancel_requested=cancel_requested,
            )
        )

    assert processor.processed_count == 1


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


def test_each_llm_plugin_calls_llm_independently() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    llm_client = FakeLLMClient()
    create_plugin = ActionAwarePlugin(
        name="create_appointment",
        prompt="APPOINTMENT_ONLY",
        expected_action="appointment",
    )
    move_plugin = ActionAwarePlugin(
        name="move_to_folder",
        prompt="MOVE_ONLY",
        expected_action="move",
        move_message=True,
        capabilities={
            PluginCapability.REQUIRES_LLM,
            PluginCapability.MOVES_MESSAGE,
        },
    )

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=llm_client,
            plugins=[create_plugin, move_plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name="destination-folder",
            body_max_length=500,
        )
    )

    assert result.success is True
    assert len(llm_client.calls) == 2
    assert create_plugin.execute_calls == 1
    assert move_plugin.execute_calls == 1
    assert message.move_calls == 1
    plugin_results = {item.plugin_name: item for item in result.plugin_results}
    assert plugin_results["create_appointment"].success is True
    assert plugin_results["move_to_folder"].success is True


def test_share_deprecated_uses_single_shared_llm_response() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    llm_client = FakeLLMClient()
    create_plugin = ActionAwarePlugin(
        name="create_appointment",
        prompt="APPOINTMENT_ONLY",
        expected_action="appointment",
    )
    move_plugin = ActionAwarePlugin(
        name="move_to_folder",
        prompt="MOVE_ONLY",
        expected_action="move",
        capabilities={PluginCapability.REQUIRES_LLM},
    )

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=llm_client,
            plugins=[create_plugin, move_plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name=None,
            body_max_length=500,
            llm_mode="share_deprecated",
        )
    )

    assert result.success is True
    assert len(llm_client.calls) == 1
    assert create_plugin.execute_calls == 1
    assert move_plugin.execute_calls == 1
    plugin_results = {item.plugin_name: item for item in result.plugin_results}
    assert plugin_results["create_appointment"].success is True
    assert plugin_results["move_to_folder"].status == PluginExecutionStatus.SKIPPED


def test_shared_alias_maps_to_share_deprecated() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    llm_client = FakeLLMClient()
    create_plugin = ActionAwarePlugin(
        name="create_appointment",
        prompt="APPOINTMENT_ONLY",
        expected_action="appointment",
    )
    move_plugin = ActionAwarePlugin(
        name="move_to_folder",
        prompt="MOVE_ONLY",
        expected_action="move",
        capabilities={PluginCapability.REQUIRES_LLM},
    )

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=llm_client,
            plugins=[create_plugin, move_plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name=None,
            body_max_length=500,
            llm_mode="shared",
        )
    )

    assert result.success is True
    assert len(llm_client.calls) == 1


def test_llm_action_success_moves_to_destination() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    llm_client = FakeLLMClient()
    create_plugin = ActionAwarePlugin(
        name="create_appointment",
        prompt="APPOINTMENT_ONLY",
        expected_action="appointment",
    )

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=llm_client,
            plugins=[create_plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name="destination-folder",
            manual_review_destination_folder_name="manual-review-folder",
            body_max_length=500,
        )
    )

    assert result.success is True
    assert message.move_calls == 1
    assert message.move_destinations == ["destination-folder"]


def test_llm_non_action_moves_to_manual_review_destination() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    llm_client = FakeLLMClient()
    non_action_plugin = ActionAwarePlugin(
        name="move_to_folder",
        prompt="APPOINTMENT_ONLY",
        expected_action="move",
        capabilities={PluginCapability.REQUIRES_LLM},
    )

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=llm_client,
            plugins=[non_action_plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name="destination-folder",
            manual_review_destination_folder_name="manual-review-folder",
            body_max_length=500,
        )
    )

    assert result.success is True
    assert message.move_calls == 1
    assert message.move_destinations == ["manual-review-folder"]


def test_llm_failed_moves_to_manual_review_destination() -> None:
    message = DummyMessage()
    processor = _build_processor_with_stubbed_extract(message)
    llm_client = FakeLLMClient()
    failing_plugin = DummyPlugin(
        name="add_category",
        prompt="needs llm",
        execute_result=False,
        capabilities={PluginCapability.REQUIRES_LLM},
    )

    result = asyncio.run(
        processor._process_email(
            message=message,
            account_name="acc",
            llm_client=llm_client,
            plugins=[failing_plugin],
            dry_run=False,
            no_move=False,
            destination_folder_name="destination-folder",
            manual_review_destination_folder_name="manual-review-folder",
            body_max_length=500,
        )
    )

    assert result.success is True
    assert failing_plugin.execute_calls == 1
    assert message.move_calls == 1
    assert message.move_destinations == ["manual-review-folder"]


def test_process_config_file_prefers_config_relative_llm_and_plugins(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "custom"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "llm-config.yaml").write_text(
        "api_base: http://localhost:11434/v1\n",
        encoding="utf-8",
    )
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


class TestPromptProfileResolution:
    def _fake_logger(self):
        class FakeLogger:
            def warning(self, msg: str) -> None:
                self._warning_msg = msg

        return FakeLogger()

    def test_resolve_plugin_prompt_job_profile_wins(self) -> None:
        from outlook_mail_extractor.core import _resolve_plugin_prompt

        raw_config = {
            "system_prompt": "default prompt",
            "prompt_profiles": {
                "profile_a": {
                    "version": 1,
                    "system_prompt": "profile A prompt",
                },
            },
        }
        job_profiles = {"test_plugin": "profile_a"}
        logger = self._fake_logger()

        resolved = _resolve_plugin_prompt(
            "test_plugin", raw_config, job_profiles, logger
        )

        assert resolved["override_prompt"] == "profile A prompt"

    def test_resolve_plugin_prompt_default_profile_when_job_not_specified(
        self,
    ) -> None:
        from outlook_mail_extractor.core import _resolve_plugin_prompt

        raw_config = {
            "system_prompt": "default prompt",
            "default_prompt_profile": "profile_b",
            "prompt_profiles": {
                "profile_b": {
                    "version": 1,
                    "system_prompt": "default profile B prompt",
                },
            },
        }
        job_profiles: dict[str, str] = {}
        logger = self._fake_logger()

        resolved = _resolve_plugin_prompt(
            "test_plugin", raw_config, job_profiles, logger
        )

        assert resolved["override_prompt"] == "default profile B prompt"

    def test_resolve_plugin_prompt_fallback_to_system_prompt(
        self,
    ) -> None:
        from outlook_mail_extractor.core import _resolve_plugin_prompt

        raw_config = {
            "system_prompt": "fallback prompt",
        }
        job_profiles: dict[str, str] = {}
        logger = self._fake_logger()

        resolved = _resolve_plugin_prompt(
            "test_plugin", raw_config, job_profiles, logger
        )

        assert "override_prompt" not in resolved
        assert resolved["system_prompt"] == "fallback prompt"

    def test_resolve_plugin_prompt_missing_profile_warns_and_fallbacks(
        self,
    ) -> None:
        from outlook_mail_extractor.core import _resolve_plugin_prompt

        raw_config = {
            "system_prompt": "fallback prompt",
            "prompt_profiles": {
                "profile_x": {
                    "version": 1,
                    "system_prompt": "profile X",
                },
            },
        }
        job_profiles = {"test_plugin": "nonexistent_profile"}
        logger = self._fake_logger()

        resolved = _resolve_plugin_prompt(
            "test_plugin", raw_config, job_profiles, logger
        )

        assert "override_prompt" not in resolved
        assert hasattr(logger, "_warning_msg")
        assert "nonexistent_profile" in logger._warning_msg

    def test_resolve_plugin_prompt_profile_string_shorthand(self) -> None:
        from outlook_mail_extractor.core import _resolve_plugin_prompt

        raw_config = {
            "system_prompt": "default",
            "prompt_profiles": {
                "short_profile": "shorthand prompt text",
            },
        }
        job_profiles = {"test_plugin": "short_profile"}
        logger = self._fake_logger()

        resolved = _resolve_plugin_prompt(
            "test_plugin", raw_config, job_profiles, logger
        )

        assert resolved["override_prompt"] == "shorthand prompt text"

    def test_resolve_plugin_prompt_does_not_mutate_original(self) -> None:
        from outlook_mail_extractor.core import _resolve_plugin_prompt

        raw_config = {
            "system_prompt": "original",
            "prompt_profiles": {
                "profile_c": {
                    "version": 1,
                    "system_prompt": "profile C",
                },
            },
        }
        job_profiles = {"test_plugin": "profile_c"}
        logger = self._fake_logger()

        resolved = _resolve_plugin_prompt(
            "test_plugin", raw_config, job_profiles, logger
        )

        assert resolved is not raw_config
        assert "override_prompt" not in raw_config
        assert raw_config["system_prompt"] == "original"
