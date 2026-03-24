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
        "add-job-enable": _FakeSwitch(True),
        "add-job-error": _FakeStatic(),
    }
    screen.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]
    captured: dict[str, object] = {}
    screen.dismiss = lambda result: captured.setdefault("result", result)  # type: ignore[method-assign]

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
        "add-job-enable": _FakeSwitch(True),
        "add-job-error": error,
    }
    screen.query_one = lambda selector, _=None: widgets[str(selector).removeprefix("#")]  # type: ignore[method-assign]
    dismissed = {"called": False}
    screen.dismiss = lambda _result: dismissed.__setitem__("called", True)  # type: ignore[method-assign]

    screen._submit()

    assert dismissed["called"] is False
    assert "不要設定 destination" in error.content
