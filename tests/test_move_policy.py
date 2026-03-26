from outlook_mail_extractor.models import PluginExecutionStatus, PluginResult
from outlook_mail_extractor.move_policy import select_move_target


def _result(name: str, status: PluginExecutionStatus) -> PluginResult:
    return PluginResult(
        plugin_name=name, success=status == PluginExecutionStatus.SUCCESS, status=status
    )


def test_select_move_target_prefers_destination_when_llm_success() -> None:
    target = select_move_target(
        plugin_results=[_result("create_appointment", PluginExecutionStatus.SUCCESS)],
        llm_plugin_names={"create_appointment"},
        destination_folder_name="done",
        manual_review_destination_folder_name="review",
        success=True,
    )

    assert target == "done"


def test_select_move_target_uses_manual_review_for_non_action() -> None:
    target = select_move_target(
        plugin_results=[_result("move_to_folder", PluginExecutionStatus.SKIPPED)],
        llm_plugin_names={"move_to_folder"},
        destination_folder_name="done",
        manual_review_destination_folder_name="review",
        success=True,
    )

    assert target == "review"


def test_select_move_target_without_llm_results_uses_destination() -> None:
    target = select_move_target(
        plugin_results=[],
        llm_plugin_names=set(),
        destination_folder_name="done",
        manual_review_destination_folder_name="review",
        success=True,
    )

    assert target == "done"
