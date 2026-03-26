import importlib


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
