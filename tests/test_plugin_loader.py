from outlook_mail_extractor.plugins.base import list_plugins
from outlook_mail_extractor.plugins.loader import load_builtin_plugins


def test_load_builtin_plugins_registers_known_plugins() -> None:
    load_builtin_plugins()
    plugins = set(list_plugins())
    assert "add_category" in plugins
    assert "event_table" in plugins


def test_load_builtin_plugins_is_idempotent() -> None:
    load_builtin_plugins()
    first = set(list_plugins())

    load_builtin_plugins()
    second = set(list_plugins())
    assert first == second
