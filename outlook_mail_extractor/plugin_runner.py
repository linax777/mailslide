"""Plugin execution helpers for EmailProcessor orchestration."""

from typing import Any

from .models import (
    DomainError,
    InfrastructureError,
    PluginExecutionResult,
    PluginExecutionStatus,
    PluginResult,
    UserVisibleError,
)
from .plugins import PluginCapability


def normalize_plugin_execution_result(
    plugin_name: str,
    execute_result: bool | PluginExecutionResult,
) -> PluginExecutionResult:
    """Normalize legacy bool plugin returns into structured results."""
    if isinstance(execute_result, PluginExecutionResult):
        return execute_result

    if execute_result:
        return PluginExecutionResult(
            status=PluginExecutionStatus.SUCCESS,
            message="Success",
        )

    return PluginExecutionResult(
        status=PluginExecutionStatus.FAILED,
        code="legacy_false",
        message=f"Plugin {plugin_name} returned False",
    )


def build_plugin_result(
    plugin_name: str,
    execute_result: bool | PluginExecutionResult,
) -> PluginResult:
    """Build PluginResult from legacy/new plugin result types."""
    normalized = normalize_plugin_execution_result(plugin_name, execute_result)
    return PluginResult(
        plugin_name=plugin_name,
        success=normalized.success,
        status=normalized.status,
        code=normalized.code,
        message=normalized.message,
        details=normalized.details,
    )


def log_plugin_result(logger: Any, plugin_result: PluginResult) -> None:
    """Log plugin execution result in a consistent style."""
    plugin_name = plugin_result.plugin_name
    if plugin_result.status == PluginExecutionStatus.SUCCESS:
        logger.info(f"Plugin {plugin_name}: success")
    elif plugin_result.status == PluginExecutionStatus.SKIPPED:
        logger.info(f"Plugin {plugin_name}: skipped ({plugin_result.message})")
    else:
        logger.warning(
            f"Plugin {plugin_name}: {plugin_result.status.value} "
            f"({plugin_result.message})"
        )


async def execute_plugin(
    plugin: Any,
    email_data: Any,
    llm_response: str,
    action_port: Any,
    logger: Any,
) -> tuple[PluginResult, bool]:
    """Execute a plugin with typed error wrapping and result normalization."""
    try:
        plugin_execute_result = await plugin.execute(
            email_data, llm_response, action_port
        )
        plugin_result = build_plugin_result(plugin.name, plugin_execute_result)
    except (DomainError, InfrastructureError, UserVisibleError) as error:
        logger.exception(f"Plugin {plugin.name} error: {error}")
        plugin_result = PluginResult(
            plugin_name=plugin.name,
            success=False,
            status=PluginExecutionStatus.FAILED,
            code="typed_error",
            message=f"Error: {error}",
        )
    except Exception as error:
        wrapped = InfrastructureError(
            f"Unhandled plugin error ({plugin.name}): {error}"
        )
        logger.exception(str(wrapped))
        plugin_result = PluginResult(
            plugin_name=plugin.name,
            success=False,
            status=PluginExecutionStatus.RETRIABLE_FAILED,
            code="unhandled_error",
            message=f"Error: {wrapped}",
        )

    moved_by_plugin = (
        plugin.supports(PluginCapability.MOVES_MESSAGE) and plugin_result.success
    )
    log_plugin_result(logger, plugin_result)
    return plugin_result, moved_by_plugin
