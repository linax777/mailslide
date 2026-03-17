# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, with entries grouped by release date.

## [2026-03-17]

### Fixed

- Fixed the `outlook-extract` console entry point so the CLI runs correctly instead of returning an un-awaited coroutine.
- Fixed `--no-move` so CLI runs can extract mail data without moving processed messages.
- Fixed cleanup in the processing pipeline to avoid masking the original exception when Outlook or LLM setup fails early.
- Fixed calendar creation to resolve the default Calendar folder from the configured Outlook account instead of the global default mailbox.
- Fixed the scheduler lifecycle in the Textual UI to stop duplicate interval timers from accumulating and to shut them down cleanly on unmount.
- Fixed the scheduler shutdown crash caused by `_schedule_timer` being initialized on the wrong screen class.
- Fixed job message limiting so `limit` now counts actual mail items only, while folders with no mail items complete normally without raising errors.
- Fixed Outlook account resolution to use strict store-name matching, so invalid account names are detected reliably instead of being accepted by ambiguous COM lookup behavior.

### Changed

- Improved email body extraction to prefer cleaned HTML content when available, preserve paragraph structure, and trim quoted reply history before sending content to the LLM pipeline.
- Improved parser cleanup with high-confidence signature and newsletter footer stripping to reduce noise in extracted email bodies.
- Improved first-run onboarding in the TUI so missing `config/config.yaml` now redirects users to the `About` tab, shows initialization guidance, and disables job execution until setup is completed.
- Improved validation in the `About` tab so system checks now verify enabled jobs' `account` and `source` settings before execution.
- Improved job execution so configured `destination` folders are created automatically when missing, which helps first-time runs on new hosts.
