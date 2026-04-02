from types import SimpleNamespace
from typing import Any

from outlook_mail_extractor.tui import OutlookMailExtractor


def test_app_home_tab_activation_requests_home_auto_refresh(
    monkeypatch: Any,
) -> None:
    app = OutlookMailExtractor()
    calls = {"count": 0}
    fake_home = SimpleNamespace(
        request_auto_refresh_on_entry=lambda: calls.__setitem__(
            "count", calls["count"] + 1
        )
    )

    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: fake_home)

    event = SimpleNamespace(pane=SimpleNamespace(id="home"))
    app.on_tabbed_content_tab_activated(event)  # type: ignore[arg-type]

    assert calls["count"] == 1


def test_app_non_home_tab_activation_does_not_request_home_auto_refresh(
    monkeypatch: Any,
) -> None:
    app = OutlookMailExtractor()
    calls = {"count": 0}
    fake_home = SimpleNamespace(
        request_auto_refresh_on_entry=lambda: calls.__setitem__(
            "count", calls["count"] + 1
        )
    )

    monkeypatch.setattr(app, "query_one", lambda *_args, **_kwargs: fake_home)

    event = SimpleNamespace(pane=SimpleNamespace(id="config"))
    app.on_tabbed_content_tab_activated(event)  # type: ignore[arg-type]

    assert calls["count"] == 0


def test_action_show_tab_updates_tabbed_content_active(monkeypatch: Any) -> None:
    app = OutlookMailExtractor()
    tabbed_content = SimpleNamespace(active="config")

    monkeypatch.setattr(app, "get_child_by_type", lambda _widget: tabbed_content)

    app.action_show_tab("home")

    assert tabbed_content.active == "home"
