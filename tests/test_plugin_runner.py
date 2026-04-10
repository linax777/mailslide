import asyncio

import pytest

from outlook_mail_extractor.models import (
    DomainError,
    EmailDTO,
    PluginExecutionResult,
    PluginExecutionStatus,
)
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

    def __init__(
        self,
        result: PluginExecutionResult | bool | None = None,
        raise_error: Exception | None = None,
    ) -> None:
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


def _success_result(message: str = "Success") -> PluginExecutionResult:
    return PluginExecutionResult(
        status=PluginExecutionStatus.SUCCESS,
        message=message,
    )


def test_normalize_plugin_execution_result_accepts_structured_result() -> None:
    result = _success_result("ok")
    normalized = normalize_plugin_execution_result("p", result)

    assert normalized is result


def test_normalize_plugin_execution_result_rejects_legacy_bool() -> None:
    with pytest.raises(TypeError, match="must return PluginExecutionResult"):
        normalize_plugin_execution_result("p", True)  # type: ignore[arg-type]


def test_execute_plugin_sets_moved_by_plugin_when_success() -> None:
    plugin_result, moved = asyncio.run(
        execute_plugin(
            _Plugin(result=_success_result()),
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


def test_execute_plugin_maps_invalid_result_contract_to_failed() -> None:
    plugin_result, moved = asyncio.run(
        execute_plugin(
            _Plugin(result=True),
            EmailDTO("s", "f", "r", "b", []),
            "",
            object(),
            _DummyLogger(),
        )
    )

    assert moved is False
    assert plugin_result.status == PluginExecutionStatus.FAILED
    assert plugin_result.code == "invalid_plugin_result_type"
    assert "must return PluginExecutionResult" in plugin_result.message


def test_execute_plugin_keeps_runtime_typeerror_as_retriable_failed() -> None:
    plugin_result, moved = asyncio.run(
        execute_plugin(
            _Plugin(raise_error=TypeError("runtime type error")),
            EmailDTO("s", "f", "r", "b", []),
            "",
            object(),
            _DummyLogger(),
        )
    )

    assert moved is False
    assert plugin_result.status == PluginExecutionStatus.RETRIABLE_FAILED
    assert plugin_result.code == "unhandled_error"
    assert "runtime type error" in plugin_result.message


def test_build_plugin_result_from_structured_result() -> None:
    result = build_plugin_result("write_file", _success_result("done"))
    assert result.plugin_name == "write_file"
    assert result.status == PluginExecutionStatus.SUCCESS
