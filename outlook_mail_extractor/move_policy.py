"""Move destination decision policy for processed emails."""

from .models import PluginExecutionStatus, PluginResult


def select_move_target(
    *,
    plugin_results: list[PluginResult],
    llm_plugin_names: set[str],
    destination_folder_name: str | None,
    manual_review_destination_folder_name: str | None,
    success: bool,
) -> str | None:
    """Select destination folder based on plugin outcomes and success state."""
    llm_plugin_results = [
        result for result in plugin_results if result.plugin_name in llm_plugin_names
    ]
    has_llm_plugin_results = bool(llm_plugin_results)
    has_llm_success = any(
        result.status == PluginExecutionStatus.SUCCESS for result in llm_plugin_results
    )
    has_llm_non_action = any(
        result.status
        in {
            PluginExecutionStatus.SKIPPED,
            PluginExecutionStatus.FAILED,
            PluginExecutionStatus.RETRIABLE_FAILED,
        }
        for result in llm_plugin_results
    )

    if has_llm_plugin_results:
        if has_llm_success and destination_folder_name:
            return destination_folder_name
        if (
            not has_llm_success
            and has_llm_non_action
            and manual_review_destination_folder_name
        ):
            return manual_review_destination_folder_name
        if destination_folder_name and success:
            return destination_folder_name
        return None

    if destination_folder_name and success:
        return destination_folder_name

    return None
