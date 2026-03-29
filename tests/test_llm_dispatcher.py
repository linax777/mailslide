import asyncio
from types import SimpleNamespace

import pytest

from outlook_mail_extractor.llm_dispatcher import (
    LLM_MODE_SHARE_DEPRECATED,
    dispatch_llm_plugins,
    resolve_llm_mode,
)
from outlook_mail_extractor.models import EmailDTO, PluginExecutionStatus
from outlook_mail_extractor.plugins import PluginCapability


class _Logger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def info(self, _message: str) -> None:
        pass

    def debug(self, _message: str) -> None:
        pass

    def error(self, _message: str) -> None:
        pass

    def exception(self, _message: str) -> None:
        pass


class _Plugin:
    def __init__(self, name: str, prompt: str) -> None:
        self.name = name
        self._prompt = prompt
        self.config = SimpleNamespace(enabled=True)

    def build_effective_prompt(self) -> str:
        return self._prompt

    def supports(self, capability: PluginCapability) -> bool:
        return capability in {
            PluginCapability.REQUIRES_LLM,
            PluginCapability.MOVES_MESSAGE,
        }

    def should_skip_by_response(self, _llm_response: str):
        return None

    async def execute(self, email_data: EmailDTO, llm_response: str, action_port):
        del email_data
        del llm_response
        del action_port
        return True


class _LLM:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def chat(self, system_prompt: str, _user_prompt: str) -> str:
        self.calls.append(system_prompt)
        return '{"action":"ok"}'


def test_resolve_llm_mode_maps_alias_and_warns() -> None:
    logger = _Logger()
    mode = resolve_llm_mode("shared", logger)

    assert mode == LLM_MODE_SHARE_DEPRECATED
    assert logger.warnings


def test_dispatch_llm_plugins_without_client_marks_unavailable() -> None:
    logger = _Logger()
    plugin = _Plugin("move_to_folder", "MOVE_ONLY")

    result = asyncio.run(
        dispatch_llm_plugins(
            plugins=[plugin],
            llm_client=None,
            user_prompt="u",
            llm_mode="per_plugin",
            dry_run=False,
            email_data=EmailDTO("s", "f", "r", "b", []),
            action_port=object(),
            logger=logger,
        )
    )

    assert result.success is False
    assert result.plugin_results[0].status == PluginExecutionStatus.FAILED
    assert result.plugin_results[0].code == "llm_unavailable"
    assert result.llm_call_count == 0


def test_dispatch_llm_plugins_per_plugin_calls_llm_once_per_plugin() -> None:
    logger = _Logger()
    llm = _LLM()
    plugins = [_Plugin("a", "A"), _Plugin("b", "B")]

    result = asyncio.run(
        dispatch_llm_plugins(
            plugins=plugins,
            llm_client=llm,
            user_prompt="u",
            llm_mode="per_plugin",
            dry_run=False,
            email_data=EmailDTO("s", "f", "r", "b", []),
            action_port=object(),
            logger=logger,
        )
    )

    assert result.success is True
    assert len(llm.calls) == 2
    assert len(result.plugin_results) == 2
    assert result.llm_call_count == 2
    assert result.llm_elapsed_ms >= 0


def test_dispatch_llm_plugins_honors_cancellation_between_plugins() -> None:
    logger = _Logger()
    llm = _LLM()
    execution_state = {"first_done": False}

    class _CancelMarkerPlugin(_Plugin):
        async def execute(self, email_data: EmailDTO, llm_response: str, action_port):
            execution_state["first_done"] = True
            return await super().execute(email_data, llm_response, action_port)

    plugins = [_CancelMarkerPlugin("a", "A"), _Plugin("b", "B")]

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            dispatch_llm_plugins(
                plugins=plugins,
                llm_client=llm,
                user_prompt="u",
                llm_mode="per_plugin",
                dry_run=False,
                email_data=EmailDTO("s", "f", "r", "b", []),
                action_port=object(),
                logger=logger,
                cancel_requested=lambda: execution_state["first_done"],
            )
        )

    assert len(llm.calls) == 1
