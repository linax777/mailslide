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


def test_footer_visible_actions_for_home_context(monkeypatch: Any) -> None:
    app = OutlookMailExtractor()
    monkeypatch.setattr(app, "_resolve_footer_context", lambda: "home")

    actions = app.get_footer_visible_actions()

    assert "confirm_quit" in actions
    assert "show_tab('config')" in actions
    assert "show_tab('schedule')" in actions


def test_footer_visible_actions_for_plugin_modal_context(monkeypatch: Any) -> None:
    app = OutlookMailExtractor()
    monkeypatch.setattr(app, "_resolve_footer_context", lambda: "modal.plugin_editor")

    actions = app.get_footer_visible_actions()

    assert "confirm_quit" in actions
    assert "show_tab('home')" not in actions


def test_resolve_footer_context_falls_back_to_last_top_tab_when_tabbed_not_available(
    monkeypatch: Any,
) -> None:
    app = OutlookMailExtractor()
    app._last_top_tab = "usage"

    def raise_no_tabbed(_widget: Any) -> Any:
        raise RuntimeError("no tabbed content")

    monkeypatch.setattr(app, "get_child_by_type", raise_no_tabbed)

    assert app._resolve_footer_context() == "usage"


def test_resolve_footer_context_falls_back_to_last_config_tab_when_config_not_available(
    monkeypatch: Any,
) -> None:
    app = OutlookMailExtractor()
    app._last_top_tab = "config"
    app._last_config_tab = "llm"

    def raise_no_tabbed(_widget: Any) -> Any:
        raise RuntimeError("no tabbed content")

    monkeypatch.setattr(app, "get_child_by_type", raise_no_tabbed)
    monkeypatch.setattr(
        app,
        "query_one",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("no config")),
    )

    assert app._resolve_footer_context() == "config.llm"
