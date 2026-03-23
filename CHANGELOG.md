# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, with entries grouped by release date.

## [v0.2.6] - 2026-03-23

### Changed

- Changed LLM plugin orchestration default to `per_plugin`, so each LLM-enabled plugin now gets its own `llm_client.chat(...)` call and response parsing path, avoiding cross-plugin `action` collisions when multiple plugins are enabled in one job.
- Added backward-compatible legacy mode `share_deprecated` that restores shared single-response behavior for migration scenarios, with explicit runtime warnings that this mode can cause `action_mismatch/skipped` outcomes across mixed-action plugins.
- Added `llm_mode` support at both config scopes (`config.llm_mode` default + `job.llm_mode` override), with runtime resolution and alias mapping from legacy values (`shared`, `shared_legacy`) to `share_deprecated`.
- Updated job execution wiring to pass global `llm_mode` defaults into processor dispatch while allowing per-job overrides without changing existing plugin config loading behavior.
- Updated `config/config.yaml.sample` and README documentation to describe `llm_mode`, recommended default usage (`per_plugin`), and deprecation guidance for shared-response mode.

### Added

- Added config validation rules for `llm_mode` values in both top-level config and per-job settings, including backward-compatible acceptance of legacy alias values.
- Added high-risk orchestration tests covering per-plugin independent LLM calls, `share_deprecated` single-call behavior, and alias compatibility (`shared` -> `share_deprecated`) in `tests/test_core_high_risk.py`.

## [v0.2.4] - 2026-03-23


## [v0.2.5] - 2026-03-23

### Added

- Added plugin prompt profile support so a single plugin config can define multiple prompt variants (`prompt_profiles`) with `default_prompt_profile`, and each job can select a profile via `plugin_prompt_profiles`.
- Added prompt-profile handling tests in `tests/test_core_high_risk.py` covering profile precedence, default fallback, missing-profile fallback warnings, shorthand profile values, and config immutability.
- Added `yaml` field-type tests for plugin editor payload collection, including valid parse, empty input handling, and invalid YAML errors.

### Changed

- Updated plugin runtime prompt resolution to apply profile-specific prompt overrides before plugin instantiation, while preserving legacy `system_prompt` behavior as final fallback.
- Updated `config/config.yaml.sample` and `config/plugins/add_category.yaml.sample` to document and demonstrate prompt-profile configuration.
- Extended prompt-profile sample/UI schema coverage to all built-in LLM plugins (`move_to_folder`, `create_appointment`, `event_table`, `summary_file`), so Plugin Configuration modal now shows the same OptionList-based profile editor for each of them.
- Updated Plugin Configuration modal UX for `prompt_profiles` editing: replaced raw YAML-only workflow with an OptionList-based profile switcher and per-profile detail editor (`version`, `description`, `system_prompt`).
- Added profile management controls in Plugin Configuration modal (`+ 新增` / `- 刪除`) to create and remove prompt profiles interactively while enforcing at least one remaining profile.
- Updated `config/config.yaml.sample` to show `plugin_prompt_profiles` under each job (per-job scope) and removed the misleading top-level example.
- Updated README with a dedicated "同 Plugin 多 Prompt（Prompt Profiles）" section describing profile structure, job-level selection, and resolution order.


## [v0.2.4] - 2026-03-23
### Fixed

- Fixed Plugin Configuration tab file discovery so backup files (`*.yaml.bak`) are no longer treated as editable plugin entries, preventing phantom `*.yaml` rows that failed with "file not found" when opened.

### Changed

- Added a new Plugin tab action button `🧹 清理備份` to remove stale plugin backup files (`config/plugins/*.yaml.bak`) and refresh the plugin list in place.
- Extended plugin-config tests to cover both backup-file filtering in the plugin list and backup cleanup behavior.


## [v0.2.3] - 2026-03-21

### Fixed

- Fixed reply/forward body cleanup so metadata header lines are consistently removed from multi-layer threads (`From/Sent/Date/To/Cc/Subject` and `寄件者/已傳送/寄件日期/收件者/收件人/副本/主旨`) even when preserving RE/FW thread content.
- Fixed reply-thread trimming behavior to keep meaningful older body text instead of dropping everything after the first separator block in common reply chains.

### Changed

- Expanded parser header pattern matching to cover colon-spacing and mixed Chinese/English variants such as `副本(CC)` and `Date:` for more stable LLM input cleanup.
- Added parser debug observability by logging pre/post cleanup body lengths during email extraction to help verify noise-reduction impact.
- Added/updated parser tests for multi-layer metadata stripping and date-header variants; current parser suite now validates this cleanup path with `uv run pytest -q tests/test_parser.py`.

## [v0.2.2] - 2026-03-20

### Highlights

- Refactored the large monolithic `screens.py` into a modular `outlook_mail_extractor/screens/` package while keeping `from outlook_mail_extractor.screens import ...` imports backward-compatible.
- Improved maintainability of schema-driven configuration UI by extracting shared YAML write/backup and validation-message helpers used across main/LLM/plugin config tabs.
- Simplified `PluginConfigEditorModal` internals by splitting dynamic form rendering and payload collection into smaller focused methods without changing runtime behavior.

### Changed

- Reorganized UI screens into dedicated modules (`about`, `home`, `schedule`, `usage`, config tabs, and modals) and removed the legacy single-file `outlook_mail_extractor/screens.py` implementation.
- Added config-tab helper modules for consistent YAML serialization/atomic write+backup behavior and reusable rule failure preview formatting.
- Kept existing TUI workflows and tests stable through refactor with no user-facing feature regression.

## [v0.2.1] - 2026-03-19

### Highlights

- Added a schema-driven configuration editing workflow in the TUI so config samples can define action buttons, field metadata, and validation rules while runtime configs remain user-editable YAML.
- Improved job authoring UX by replacing direct empty-row insertion with a modal add-job form that validates required fields before updating config content.
- Added the new `summary_file` plugin to support LLM-generated summary rows appended to a CSV output file.

### Changed

- Extended `config/*.yaml.sample` and `config/plugins/*.yaml.sample` with `_ui` metadata blocks for future form generation and centralized validation behavior.
- Updated the Configuration tab layout to prioritize the jobs list and editable config area, with schema action buttons for validate/save/add/remove/reset.
- Switched add-job plugin selection to Textual `SelectionList` driven by plugin options declared in config schema.
- Updated the Plugin Configuration tab to support schema-driven modal editing (`str/int/bool/select/textarea/path/list[str]/multiselect`), with field-level validation and `_ui.validation_rules` execution before save.
- Added plugin-config save safeguards: remove reserved metadata keys before write, and auto-create `<plugin>.yaml.bak` when overwriting an existing file.
- Refined `response_json_format` editing UX: keep `action`/`start`/`end` locked as fixed template keys while allowing other JSON example fields to be edited safely as structured inputs.
- Removed the unused LLM `provider` runtime setting from config/UI samples and status display, since execution already uses OpenAI-compatible `api_base` directly.
- Updated README with `_ui` metadata guidance and `summary_file` plugin usage examples.
- Hardened Main Config save flow in the TUI to validate editor payloads before write (`_ui.validation_rules` plus runtime `validate_config`), preventing invalid YAML objects from overwriting `config/config.yaml`.
- Added Main Config backup+atomic write behavior (`config.yaml.bak` + temp-file replace), aligning safety guarantees with existing LLM/plugin editor writes.
- Improved Main Config remove-job UX to delete the selected row when available (with fallback to last item) and updated the notification to show both removed row number and job name.

### Added

- Added `outlook_mail_extractor/ui_schema.py` helpers for loading schema metadata, flattening field definitions, evaluating validation rules, generating list-item defaults, and stripping reserved keys.
- Added `load_plugin_ui_schema` and Plugin Configuration TUI wiring to load plugin `_ui` schemas from `config/plugins/*.yaml.sample` with read-only fallback when schema is missing.
- Added `config/plugins/summary_file.yaml.sample`, `outlook_mail_extractor/plugins/summary_file.py`, and `tests/test_summary_file_plugin.py` for the summary CSV plugin workflow.
- Added `tests/test_ui_schema.py` coverage for schema field flattening, rule evaluation, default list-item generation, reserved-key stripping, and plugin schema loading.
- Added `tests/test_plugin_config_editor.py` coverage for modal payload mapping/validation and plugin config file backup-write behavior.
- Added `tests/test_main_config_editor.py` coverage for Main Config editor payload validation and backup/atomic write behavior.

## [v0.2.0] - 2026-03-19

### Highlights

- Completed architecture improvement milestones PR-1 through PR-7, including service extraction, typed error layering, structured plugin results, capability-based plugin dispatch, DTO/action-port boundaries, and runtime-context dependency injection.
- Unified CLI/TUI behavior through shared execution and preflight services, reducing duplicated UI business logic and improving consistency.
- Improved testability and maintainability by replacing hardcoded paths/global state with injectable runtime dependencies and by expanding automated test coverage.

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
- Introduced `EmailDTO` and `MailActionPort` to separate domain email data from Outlook COM side effects, and added `OutlookMailActionAdapter` as the infrastructure implementation.
- Refactored `EmailProcessor` and built-in plugins to use the action port boundary instead of hidden `_message`/`_account` fields, so plugin behavior can be tested with fake ports without COM dependencies.
- Updated plugin/core tests to validate the new DTO + action-port flow and preserve existing processing behavior.
- Introduced runtime dependency wiring via `RuntimeContext`/`RuntimePaths` and updated CLI/TUI flows to consume injected paths, logger manager, and client factory instead of hardcoded module-level paths.
- Refactored logger state into an injectable `LogSessionManager` while keeping `LoggerManager` as a backward-compatible static facade.
- Extended `core.process_config_file` and `JobExecutionService` dependency injection points (runtime paths + logger + factories/loaders), reducing monkeypatch needs in tests.

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
