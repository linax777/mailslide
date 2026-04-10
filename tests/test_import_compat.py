import importlib
from contextlib import contextmanager
import sys
import warnings


def _is_compat_module(name: str) -> bool:
    return (
        name == "mailslide"
        or name.startswith("mailslide.")
        or name == "outlook_mail_extractor"
        or name.startswith("outlook_mail_extractor.")
    )


@contextmanager
def _isolated_compat_imports():
    snapshot = {
        name: module for name, module in sys.modules.items() if _is_compat_module(name)
    }
    for name in list(snapshot):
        sys.modules.pop(name, None)

    try:
        yield
    finally:
        for name in [name for name in list(sys.modules) if _is_compat_module(name)]:
            sys.modules.pop(name, None)
        sys.modules.update(snapshot)


def test_import_mailslide_available() -> None:
    module = importlib.import_module("mailslide")
    assert hasattr(module, "__version__")


def test_versions_match_between_paths() -> None:
    legacy = importlib.import_module("outlook_mail_extractor")
    current = importlib.import_module("mailslide")
    assert current.__version__ == legacy.__version__


def test_legacy_import_still_available() -> None:
    legacy = importlib.import_module("outlook_mail_extractor")
    assert hasattr(legacy, "load_config")


def test_legacy_import_emits_deprecation_warning(monkeypatch) -> None:
    monkeypatch.setenv("MAILSLIDE_IMPORT_WARNING", "1")
    with _isolated_compat_imports(), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        compat = importlib.import_module("mailslide._compat")
        importlib.import_module("outlook_mail_extractor")

    messages = [str(item.message) for item in caught]
    assert compat.LEGACY_IMPORT_MESSAGE in messages


def test_mailslide_import_does_not_emit_legacy_warning(monkeypatch) -> None:
    monkeypatch.setenv("MAILSLIDE_IMPORT_WARNING", "1")
    with _isolated_compat_imports(), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        importlib.import_module("mailslide")

    messages = [str(item.message).lower() for item in caught]
    assert not any("deprecated" in message for message in messages)


def test_mailslide_star_import_keeps_legacy_exports() -> None:
    namespace: dict[str, object] = {}
    exec("from mailslide import *", {}, namespace)
    assert "load_config" in namespace
    assert "EmailProcessor" in namespace
    assert "__version__" in namespace


def test_mailslide_all_keeps_legacy_export_parity() -> None:
    legacy = importlib.import_module("outlook_mail_extractor")
    current = importlib.import_module("mailslide")

    expected = set(getattr(legacy, "__all__", []))
    expected.add("__version__")
    assert set(current.__all__) == expected


def test_mailslide_version_source_is_canonical(monkeypatch) -> None:
    legacy = importlib.import_module("outlook_mail_extractor")
    current = importlib.import_module("mailslide")
    canonical_version = current.__version__

    monkeypatch.setattr(legacy, "__version__", "legacy-overridden")
    reloaded = importlib.reload(current)

    assert reloaded.__version__ == canonical_version
