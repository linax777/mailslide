from typing import Any

from outlook_mail_extractor.screens.modals.add_job import AddJobScreen


class _FakeInput:
    def __init__(self, value: str):
        self.value = value


class _FakeSwitch:
    def __init__(self, value: bool):
        self.value = value


class _FakeSelectionList:
    def __init__(self, selected: list[str]):
        self.selected = selected


class _FakeStatic:
    def __init__(self) -> None:
        self.content = ""

    def update(self, content: str) -> None:
        self.content = content


def test_add_job_modal_submit_includes_manual_review_destination() -> None:
    screen = AddJobScreen(plugin_options=["add_category", "move_to_folder"])
    widgets: dict[str, Any] = {
        "add-job-name": _FakeInput("job-a"),
        "add-job-account": _FakeInput("a@example.com"),
        "add-job-source": _FakeInput("Inbox"),
        "add-job-destination": _FakeInput("Inbox/processed"),
        "add-job-manual-review-destination": _FakeInput("Inbox/manual_review"),
        "add-job-limit": _FakeInput("10"),
        "add-job-plugins": _FakeSelectionList(["add_category"]),
        "add-job-plugin-profile-add_category": _FakeInput(""),
        "add-job-plugin-profile-move_to_folder": _FakeInput(""),
        "add-job-enable": _FakeSwitch(True),
        "add-job-error": _FakeStatic(),
    }
    screen.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]
    captured: dict[str, object] = {}
    screen.dismiss = lambda result: captured.setdefault("result", result)  # type: ignore[assignment,misc,method-assign]

    screen._submit()

    result = captured["result"]
    assert isinstance(result, dict)
    assert result["manual_review_destination"] == "Inbox/manual_review"
    assert result["plugins"] == ["add_category"]


def test_add_job_modal_submit_blocks_move_plugin_with_destination() -> None:
    screen = AddJobScreen(plugin_options=["move_to_folder"])
    error = _FakeStatic()
    widgets: dict[str, Any] = {
        "add-job-name": _FakeInput("job-a"),
        "add-job-account": _FakeInput("a@example.com"),
        "add-job-source": _FakeInput("Inbox"),
        "add-job-destination": _FakeInput("Inbox/processed"),
        "add-job-manual-review-destination": _FakeInput("Inbox/manual_review"),
        "add-job-limit": _FakeInput("10"),
        "add-job-plugins": _FakeSelectionList(["move_to_folder"]),
        "add-job-plugin-profile-move_to_folder": _FakeInput(""),
        "add-job-enable": _FakeSwitch(True),
        "add-job-error": error,
    }
    screen.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]
    dismissed = {"called": False}
    screen.dismiss = lambda _result: dismissed.__setitem__("called", True)  # type: ignore[assignment,misc,method-assign]

    screen._submit()

    assert dismissed["called"] is False
    assert (
        "不要設定 destination" in error.content
        or "Do not set destination" in error.content
    )


def test_add_job_modal_submit_includes_plugin_prompt_profiles() -> None:
    screen = AddJobScreen(
        plugin_options=["add_category", "create_appointment", "move_to_folder"]
    )
    widgets: dict[str, Any] = {
        "add-job-name": _FakeInput("job-a"),
        "add-job-account": _FakeInput("a@example.com"),
        "add-job-source": _FakeInput("Inbox"),
        "add-job-destination": _FakeInput(""),
        "add-job-manual-review-destination": _FakeInput(""),
        "add-job-limit": _FakeInput("10"),
        "add-job-plugins": _FakeSelectionList(["add_category", "create_appointment"]),
        "add-job-plugin-profile-add_category": _FakeInput("invoice_v1"),
        "add-job-plugin-profile-create_appointment": _FakeInput("meeting_v2"),
        "add-job-plugin-profile-move_to_folder": _FakeInput("routing_v1"),
        "add-job-enable": _FakeSwitch(True),
        "add-job-error": _FakeStatic(),
    }
    screen.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]
    captured: dict[str, object] = {}
    screen.dismiss = lambda result: captured.setdefault("result", result)  # type: ignore[assignment,misc,method-assign]

    screen._submit()

    result = captured["result"]
    assert isinstance(result, dict)
    assert result["plugins"] == ["add_category", "create_appointment"]
    assert result["plugin_prompt_profiles"] == {
        "add_category": "invoice_v1",
        "create_appointment": "meeting_v2",
    }


def test_add_job_modal_submit_ignores_unselected_plugin_profile() -> None:
    screen = AddJobScreen(plugin_options=["add_category", "create_appointment"])
    widgets: dict[str, Any] = {
        "add-job-name": _FakeInput("job-a"),
        "add-job-account": _FakeInput("a@example.com"),
        "add-job-source": _FakeInput("Inbox"),
        "add-job-destination": _FakeInput(""),
        "add-job-manual-review-destination": _FakeInput(""),
        "add-job-limit": _FakeInput("10"),
        "add-job-plugins": _FakeSelectionList(["add_category"]),
        "add-job-plugin-profile-add_category": _FakeInput("invoice_v1"),
        "add-job-plugin-profile-create_appointment": _FakeInput("meeting_v2"),
        "add-job-enable": _FakeSwitch(True),
        "add-job-error": _FakeStatic(),
    }
    screen.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]
    captured: dict[str, object] = {}
    screen.dismiss = lambda result: captured.setdefault("result", result)  # type: ignore[assignment,misc,method-assign]

    screen._submit()

    result = captured["result"]
    assert isinstance(result, dict)
    assert result["plugins"] == ["add_category"]
    assert result["plugin_prompt_profiles"] == {"add_category": "invoice_v1"}


def test_add_job_modal_submit_preserves_unavailable_selected_plugin() -> None:
    screen = AddJobScreen(
        plugin_options=["download_attachments", "legacy_plugin"],
        unavailable_plugins=["legacy_plugin"],
    )
    widgets: dict[str, Any] = {
        "add-job-name": _FakeInput("job-a"),
        "add-job-account": _FakeInput("a@example.com"),
        "add-job-source": _FakeInput("Inbox"),
        "add-job-destination": _FakeInput(""),
        "add-job-manual-review-destination": _FakeInput(""),
        "add-job-limit": _FakeInput("10"),
        "add-job-plugins": _FakeSelectionList(
            ["download_attachments", "legacy_plugin"]
        ),
        "add-job-plugin-profile-download_attachments": _FakeInput(""),
        "add-job-plugin-profile-legacy_plugin": _FakeInput(""),
        "add-job-enable": _FakeSwitch(True),
        "add-job-error": _FakeStatic(),
    }
    screen.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]
    captured: dict[str, object] = {}
    screen.dismiss = lambda result: captured.setdefault("result", result)  # type: ignore[assignment,misc,method-assign]

    screen._submit()

    result = captured["result"]
    assert isinstance(result, dict)
    assert result["plugins"] == ["download_attachments", "legacy_plugin"]


def test_add_job_modal_marks_unavailable_plugin_in_label() -> None:
    screen = AddJobScreen(
        plugin_options=["legacy_plugin"],
        unavailable_plugins=["legacy_plugin"],
    )

    label = screen._plugin_option_label("legacy_plugin")

    assert "legacy_plugin" in label
    assert "unavailable" in label or "不可用" in label
