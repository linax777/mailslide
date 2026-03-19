# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, with entries grouped by release date.

## [2026-03-19]

### Fixed

- Fixed `event_table` CSV schema handling by making column definitions code-fixed and ignoring user-provided `fields` overrides, with a warning log for deprecated config keys.
- Fixed `event_table` datetime parsing to accept ISO8601 timestamps with timezone offsets (for example `+08:00`) and UTC `Z` suffixes.
- Fixed `create_appointment` datetime parsing to accept ISO8601 timezone timestamps and normalize them to Outlook-COM-safe naive datetimes before appointment creation.

### Changed

- Introduced `JobExecutionService` to own config-driven job orchestration, and refactored `core.process_config_file` into a thin compatibility wrapper while aligning CLI/TUI execution paths to the shared service.
- Added plugin capability-based dispatch (`requires_llm`, `can_skip_by_response`, `moves_message`) so orchestrator behavior is declared by plugin capabilities instead of hardcoded plugin names.
- Updated built-in plugins to declare capabilities and moved appointment skip logic (`create=false`) into the `create_appointment` plugin via a response-based skip hook.
- Added `mypy` to the dev dependency group, installed typing stubs (`types-pyyaml`, `types-pywin32`), and introduced project mypy config (including `pycron` missing-stub override) so static typing checks can run in CI/local workflows.
- Applied targeted typing improvements in core/services/tests to make `uv run mypy .` pass without changing runtime behavior.
- Added plugin tests covering timezone datetime handling in both `event_table` CSV export and `create_appointment` calendar creation flows.
- Removed the legacy `outlook_worker.py` compatibility script because the project now uses `outlook_mail_extractor.__main__` as the single CLI entry point.
- Updated `.gitignore` and git tracking so local workflow notes (`AGENTS.md`, `DEVELOPER.md`, `tasks/`) stay untracked.
- Introduced application-level error layering (`AppError`, `DomainError`, `InfrastructureError`, `UserVisibleError`) and aligned core processing error handling to preserve typed failures while wrapping unknown exceptions as infrastructure-level errors.
- Introduced structured plugin execution results via `PluginExecutionResult` and `PluginExecutionStatus` (`success`, `skipped`, `failed`, `retriable_failed`) to improve plugin observability and diagnostics.
- Updated `EmailProcessor` orchestration to normalize both legacy `bool` plugin returns and new structured results, preserving backward compatibility while standardizing plugin logs and result metadata.
- Migrated built-in plugins (`create_appointment`, `move_to_folder`, `add_category`, `event_table`, `write_file`) to return structured execution outcomes with explicit status codes/messages.
- Added a shared `PreflightCheckService` for validating enabled jobs against Outlook account/source availability, and refactored TUI pre-run + About checks to use this common service.
- Added CLI preflight validation before job execution (with `--skip-preflight` escape hatch) so command-line runs now catch account/source config issues early.
- Added unit tests for preflight validation behavior (`tests/test_preflight_service.py`) and cleaned related UI lint warnings while wiring the new service.

## [2026-03-18]

### Fixed

- Fixed OpenAI-compatible endpoint joining in the LLM client by using a relative `chat/completions` path, so configured `api_base` paths (for example `/v1`) are no longer dropped.
- Fixed LLM API base handling by normalizing `api_base` (trim + single trailing slash), preventing malformed URL joins across local providers such as LM Studio.
- Fixed LLM HTTP error reporting to include server-side error details and request URL context, making `400` and upstream timeout (`504`) diagnosis actionable in UI/CLI logs.
- Fixed Home-tab execution controls by adding a dedicated stop button that cancels the running worker and restores run/stop button states cleanly after cancellation or completion.
- Fixed job execution flow so `destination` moving still works when no LLM client is available and no-LLM plugins (such as `write_file`) still execute instead of exiting early.
- Fixed duplicate move behavior by skipping final `destination` moving when `move_to_folder` has already moved the message.
- Fixed config-relative loading by resolving `llm-config.yaml` and `plugins/` from the provided `--config` directory first, with fallback to default `config/` paths.
- Fixed parser reply-history behavior so `preserve_reply_thread=True` now keeps reply metadata lines instead of removing them unconditionally.
- Fixed parser style handling for tags with non-string `style` attributes to avoid attribute access/type-check issues during HTML cleanup.

### Changed

- Added `pytest` to the dev dependency group and lockfile so `uv run pytest` works without temporary dependency flags.
- Added a new `event_table` plugin that reuses appointment-style LLM extraction and appends event rows to a single CSV table (`output/events.csv`) instead of creating Outlook calendar items.
- Added `config/plugins/event_table.yaml.sample` and README documentation for configuring CSV output path and column order.
- Updated the About screen version label to `0.1.7`.
- Updated `.gitignore` to keep user-local `config/*.yaml` and `config/plugins/*.yaml` ignored while allowing `tests/` to be tracked in git.

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
- Fixed the no-LLM plugin execution path (e.g., `write_file`) so processed messages are still moved to the configured destination folder.
- Fixed an `UnboundLocalError` in the no-LLM path by initializing `error_msg` before early return branches.

### Changed

- Improved email body extraction to prefer cleaned HTML content when available, preserve paragraph structure, and trim quoted reply history before sending content to the LLM pipeline.
- Updated parser body cleanup to remove reply/forward metadata header lines from content (`From/Sent/To/Cc/Subject` and `寄件者/已傳送/收件者/副本/主旨`) to reduce body noise and length.
- Improved parser cleanup with high-confidence signature and newsletter footer stripping to reduce noise in extracted email bodies.
- Improved forwarded-message parsing so short `FW:`/`Fwd:`/`轉寄` comments keep the forwarded body instead of truncating everything after the first forwarded header block.
- Added parser coverage for forwarded-message extraction and standard reply-thread trimming behavior.
- Improved first-run onboarding in the TUI so missing `config/config.yaml` now redirects users to the `About` tab, shows initialization guidance, and disables job execution until setup is completed.
- Improved validation in the `About` tab so system checks now verify enabled jobs' `account` and `source` settings before execution.
- Improved job execution so configured `destination` folders are created automatically when missing, which helps first-time runs on new hosts.
- Changed parser defaults to preserve RE/FW thread content unless explicitly disabled via `preserve_reply_thread=False`.
- Added a Home-tab toggle control for preserving RE/FW content during parsing and wired it through to the processing pipeline.
- Replaced the Home-tab switch widget with a visible ON/OFF toggle button to avoid terminal layout visibility issues.
- Added configurable `body_max_length` support in `config.yaml` (global default plus per-job override) so body truncation length can be tuned by environment.
- Updated config validation to enforce positive-integer `body_max_length` values.
- Updated `config/config.yaml.sample` with documented `body_max_length` examples.
- Updated `.gitignore` to ignore local `tests/` and `tasks/` directories.
