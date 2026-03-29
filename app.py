"""Legacy TUI launcher for source mode."""

from outlook_mail_extractor.tui import OutlookMailExtractor, main

__all__ = ["OutlookMailExtractor", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
