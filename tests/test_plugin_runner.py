import asyncio

from outlook_mail_extractor.models import DomainError, EmailDTO, PluginExecutionStatus
from outlook_mail_extractor.plugin_runner import (
    build_plugin_result,
    execute_plugin,
    normalize_plugin_execution_result,
)
from outlook_mail_extractor.plugins import PluginCapability


class _DummyLogger:
    def info(self, _message: str) -> None:
        pass

    def warning(self, _message: str) -> None:
        pass

    def exception(self, _message: str) -> None:
        pass


class _Plugin:
    name = "move_to_folder"

    def __init__(self, result=True, raise_error: Exception | None = None) -> None:
        self._result = result
        self._raise_error = raise_error

    def supports(self, capability: PluginCapability) -> bool:
        return capability == PluginCapability.MOVES_MESSAGE

    async def execute(self, email_data: EmailDTO, llm_response: str, action_port):
        del email_data
        del llm_response
        del action_port
        if self._raise_error is not None:
            raise self._raise_error
        return self._result


def test_normalize_plugin_execution_result_legacy_bool() -> None:
    success = normalize_plugin_execution_result("p", True)
    failed = normalize_plugin_execution_result("p", False)

    assert success.status == PluginExecutionStatus.SUCCESS
    assert failed.status == PluginExecutionStatus.FAILED
    assert failed.code == "legacy_false"


def test_execute_plugin_sets_moved_by_plugin_when_success() -> None:
    plugin_result, moved = asyncio.run(
        execute_plugin(
            _Plugin(result=True),
            EmailDTO("s", "f", "r", "b", []),
            "",
            object(),
            _DummyLogger(),
        )
    )

    assert moved is True
    assert plugin_result.success is True


def test_execute_plugin_wraps_typed_error() -> None:
    plugin_result, moved = asyncio.run(
        execute_plugin(
            _Plugin(raise_error=DomainError("bad request")),
            EmailDTO("s", "f", "r", "b", []),
            "",
            object(),
            _DummyLogger(),
        )
    )

    assert moved is False
    assert plugin_result.status == PluginExecutionStatus.FAILED
    assert plugin_result.code == "typed_error"
    assert "bad request" in plugin_result.message


def test_build_plugin_result_from_legacy_bool() -> None:
    result = build_plugin_result("write_file", True)
    assert result.plugin_name == "write_file"
    assert result.status == PluginExecutionStatus.SUCCESS
