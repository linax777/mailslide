"""mailslide compatibility package.

This package re-exports the public API from ``outlook_mail_extractor``
during the import-path migration period.
"""

from outlook_mail_extractor import *  # noqa: F403
from outlook_mail_extractor import __all__ as _legacy_all
from outlook_mail_extractor import __version__ as _legacy_version

__version__ = _legacy_version

__all__ = list(_legacy_all)
__all__.append("__version__")
