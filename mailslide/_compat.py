"""Compatibility helpers for legacy import paths."""

import warnings

LEGACY_IMPORT_MESSAGE = (
    "Import path 'outlook_mail_extractor' is deprecated; prefer 'mailslide'."
)


def warn_legacy_import() -> None:
    warnings.warn(LEGACY_IMPORT_MESSAGE, DeprecationWarning, stacklevel=4)
