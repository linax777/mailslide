"""LLM dispatch flow for plugin execution orchestration."""

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from .models import PluginExecutionStatus, PluginResult
from .plugin_runner import build_plugin_result, execute_plugin


LLM_MODE_PER_PLUGIN = "per_plugin"
LLM_MODE_SHARE_DEPRECATED = "share_deprecated"
LLM_MODE_ALIASES = {
    "shared": LLM_MODE_SHARE_DEPRECATED,
    "shared_legacy": LLM_MODE_SHARE_DEPRECATED,
}


def resolve_llm_mode(raw_mode: Any, logger: Any) -> str:
    """Resolve llm_mode with alias/backward compatibility handling."""
    if not isinstance(raw_mode, str) or not raw_mode.strip():
        return LLM_MODE_PER_PLUGIN

    normalized = raw_mode.strip().lower()
    if normalized == LLM_MODE_PER_PLUGIN:
        return LLM_MODE_PER_PLUGIN
    if normalized == LLM_MODE_SHARE_DEPRECATED:
        return LLM_MODE_SHARE_DEPRECATED
    if normalized in LLM_MODE_ALIASES:
        mapped = LLM_MODE_ALIASES[normalized]
        logger.warning(f"llm_mode '{raw_mode}' is deprecated; use '{mapped}' instead")
        return mapped

    logger.warning(
        f"Unknown llm_mode '{raw_mode}'; fallback to '{LLM_MODE_PER_PLUGIN}'"
    )
    return LLM_MODE_PER_PLUGIN


@dataclass
class LLMDispatchResult:
    """Outcome bundle for LLM-driven plugin dispatch."""

    llm_response: str = ""
    plugin_results: list[PluginResult] = field(default_factory=list)
    success: bool = True
    error_message: str = ""
    moved_by_plugin: bool = False
    llm_call_count: int = 0
    llm_elapsed_ms: float = 0.0


async def dispatch_llm_plugins(
    *,
    plugins: list[Any],
    llm_client: Any,
    user_prompt: str,
    llm_mode: str,
    dry_run: bool,
    email_data: Any,
    action_port: Any,
    logger: Any,
) -> LLMDispatchResult:
    """Dispatch LLM calls and execute LLM-required plugins."""
    result = LLMDispatchResult()
    if not plugins:
        return result

    if not llm_client:
        result.success = False
        result.error_message = "LLM client not available"
        logger.warning("略過需 LLM 的插件：LLM client not available")
        for plugin in plugins:
            result.plugin_results.append(
                PluginResult(
                    plugin_name=plugin.name,
                    success=False,
                    status=PluginExecutionStatus.FAILED,
                    code="llm_unavailable",
                    message="LLM client not available",
                )
            )
        return result

    resolved_llm_mode = resolve_llm_mode(llm_mode, logger)

    if resolved_llm_mode == LLM_MODE_SHARE_DEPRECATED:
        logger.warning(
            "llm_mode=share_deprecated is deprecated; prefer per_plugin to avoid action mismatch"
        )
        combined_system = "\n\n---\n\n".join(
            [plugin.build_effective_prompt() for plugin in plugins]
        )

        try:
            started_at = perf_counter()
            llm_response = llm_client.chat(combined_system, user_prompt)
            result.llm_call_count += 1
            result.llm_elapsed_ms += (perf_counter() - started_at) * 1000
            result.llm_response = llm_response
            logger.debug(f"LLM 回覆(shared): {llm_response}")
        except Exception as error:
            result.llm_call_count += 1
            result.llm_elapsed_ms += (perf_counter() - started_at) * 1000
            result.success = False
            result.error_message = str(error)
            logger.error(f"LLM 呼叫失敗: {error}")
            return result

        if dry_run:
            return result

        for plugin in plugins:
            skip_result = plugin.should_skip_by_response(result.llm_response)
            if skip_result:
                plugin_result = build_plugin_result(plugin.name, skip_result)
                result.plugin_results.append(plugin_result)
                logger.info(f"跳過 Plugin {plugin.name}: {plugin_result.message}")
                continue

            logger.info(f"執行 Plugin: {plugin.name}")
            plugin_result, moved = await execute_plugin(
                plugin,
                email_data,
                result.llm_response,
                action_port,
                logger,
            )
            result.plugin_results.append(plugin_result)
            result.moved_by_plugin = result.moved_by_plugin or moved

        return result

    llm_responses: list[str] = []
    for plugin in plugins:
        plugin_prompt = plugin.build_effective_prompt()
        plugin_llm_response = ""
        try:
            started_at = perf_counter()
            plugin_llm_response = llm_client.chat(plugin_prompt, user_prompt)
            result.llm_call_count += 1
            result.llm_elapsed_ms += (perf_counter() - started_at) * 1000
            llm_responses.append(f"[{plugin.name}]\n{plugin_llm_response}")
            logger.debug(f"LLM 回覆 ({plugin.name}): {plugin_llm_response}")
        except Exception as error:
            result.llm_call_count += 1
            result.llm_elapsed_ms += (perf_counter() - started_at) * 1000
            result.success = False
            result.error_message = str(error)
            logger.error(f"LLM 呼叫失敗 ({plugin.name}): {error}")
            result.plugin_results.append(
                PluginResult(
                    plugin_name=plugin.name,
                    success=False,
                    status=PluginExecutionStatus.FAILED,
                    code="llm_call_failed",
                    message=f"LLM call failed: {error}",
                )
            )
            continue

        if dry_run:
            continue

        skip_result = plugin.should_skip_by_response(plugin_llm_response)
        if skip_result:
            plugin_result = build_plugin_result(plugin.name, skip_result)
            result.plugin_results.append(plugin_result)
            logger.info(f"跳過 Plugin {plugin.name}: {plugin_result.message}")
            continue

        logger.info(f"執行 Plugin: {plugin.name}")
        plugin_result, moved = await execute_plugin(
            plugin,
            email_data,
            plugin_llm_response,
            action_port,
            logger,
        )
        result.plugin_results.append(plugin_result)
        result.moved_by_plugin = result.moved_by_plugin or moved

    result.llm_response = "\n\n---\n\n".join(llm_responses)
    return result
