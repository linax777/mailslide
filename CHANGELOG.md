# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, with entries grouped by release date.

## [v0.3.10rc1] - 2026-03-29

### Changed

- Changed Home-tab stop behavior to use cooperative cancellation wiring end-to-end, propagating Textual worker cancellation signals from `HomeScreen` into job orchestration (`JobExecutionService`), per-mail processing (`EmailProcessor`), and LLM/plugin dispatch checkpoints.
- Changed job/plugin lifecycle handling to preserve safe plugin finalization (`end_job`) even when cancellation occurs mid-run, while stopping new jobs/emails/plugins from starting after a stop request.
- Changed Main Configuration job modal (`新增 Job`/`修改 Job`) to expose per-plugin prompt-profile inputs, so users can set `plugin_prompt_profiles` directly in the form instead of editing YAML manually.
- Changed Plugin Configuration prompt-profile editor to allow renaming `profile key` values directly in the modal, with validation for non-empty and unique keys.
- Changed plugin-save flow to auto-sync renamed prompt-profile references in `config/config.yaml` (`jobs[].plugin_prompt_profiles`) for the edited plugin, including backup-safe writes.
- Changed Main Configuration tab to include a `Reload` action button that re-reads `config/config.yaml` from disk on demand (with schema fallback injection for older `_ui` samples that do not define the button yet).

### Fixed

- Fixed Home-tab `⏹️ 終止` / Stop button behavior where pressing stop only cancelled the UI worker but did not actually interrupt background execution; stop requests now halt execution at the next safe checkpoint (before next job, next mail, next plugin, and before each LLM call).
- Fixed prompt-profile rename propagation reliability by adding plugin-side rename inference fallback and plugin-name callback fallback, so job `plugin_prompt_profiles` references are still synchronized even when explicit rename metadata is missing.

### Added

- Added cancellation regression coverage in `tests/test_job_execution_service.py`, `tests/test_core_high_risk.py`, and `tests/test_llm_dispatcher.py` to verify stop requests prevent continued processing beyond the current safe step.
- Added modal/i18n coverage for per-plugin profile assignment in jobs, including `tests/test_add_job_modal.py` assertions for selected-plugin filtering and new locale strings in `outlook_mail_extractor/locales/zh-TW.yaml` and `outlook_mail_extractor/locales/en-US.yaml`.
- Added prompt-profile rename + job-reference sync coverage in `tests/test_plugin_config_editor.py`, plus new plugin-editor/plugin-tab i18n messages for rename validation and sync notifications.

## [v0.3.9] - 2026-03-28

### Changed

- Updated the LLM Configuration tab UI (`outlook_mail_extractor/screens/config/llm_tab.py`) to show an in-app AI mail-reading privacy warning and disclaimer directly below the LLM settings actions.
- Added localized warning/disclaimer copy for both `zh-TW` and `en-US` in `outlook_mail_extractor/locales/zh-TW.yaml` and `outlook_mail_extractor/locales/en-US.yaml` so the legal/privacy notice follows the selected UI language.
- Updated git ignore/tracking hygiene by untracking local release helper scripts (`scripts/release_pypi.ps1`, `scripts/sync_guides.ps1`) and adding them to `.gitignore`.
- Updated `event_table` Excel writing (`outlook_mail_extractor/plugins/event_table.py`) to retry when files are locked by Excel, with configurable retry count/delay (`excel_write_retries`, `excel_write_retry_delay_seconds`) and explicit lock warning logs during retries.
- Updated `event_table` config samples (`config/plugins/event_table.yaml.sample`, `outlook_mail_extractor/resources/config_samples/plugins/event_table.yaml.sample`) to expose the new Excel lock-retry settings in both runtime config and `_ui` schema.

### Fixed

- Fixed `event_table` lock contention handling so locked `.xlsx` writes now return `retriable_failed` with `code="excel_file_locked"` and a clear actionable message instead of a generic unexpected error.
- Fixed malformed `uv.lock` content that broke `uv run`/test execution by restoring a valid `[[package]]` entry for `mailslide`.

## [v0.3.8] - 2026-03-27

### Added

- Added terminal window title handling via `outlook_mail_extractor/terminal_title.py`, with Windows Console API support (`SetConsoleTitleW`) and ANSI fallback for TTY terminals.
- Added config-driven terminal title override via `terminal_title` in `config/config.yaml` (default: `Mailslide`) for both CLI (`mailslide`) and TUI (`mailslide-tui`) startup flows.
- Added terminal-title regression tests in `tests/test_terminal_title.py` covering Windows, ANSI, and config fallback behavior.

### Changed

- Updated config samples (`config/config.yaml.sample`, `outlook_mail_extractor/resources/config_samples/config.yaml.sample`) to document the new optional `terminal_title` key.

## [v0.3.7] - 2026-03-27

### Added

- Added packaged Guide documentation resources under `outlook_mail_extractor/resources/docs/` (`GUIDE.md`, `GUIDE.en.md`) so installed/tool environments can render Guide content without repository-local markdown files.
- Added `scripts/sync_guides.ps1` to sync/check root `GUIDE*.md` files against packaged docs resources, with `-CheckOnly` mode for CI/release validation.
- Added Guide loading regression coverage in `tests/test_usage_screen.py` for packaged-resource fallbacks in both `en-US` and `zh-TW` locales.

### Changed

- Changed Guide tab content loading (`outlook_mail_extractor/screens/usage.py`) to fall back to packaged docs via `importlib.resources` when filesystem Guide/README candidates are unavailable.
- Changed package data configuration (`pyproject.toml`) to include `resources/docs/*.md` in built distributions.
- Changed PyPI release preflight (`scripts/release_pypi.ps1`) to enforce Guide resource sync before tests/build.

## [v0.3.6] - 2026-03-27

### Added

- Added a Home-tab run-status ASCII animation above the jobs table (`outlook_mail_extractor/screens/home.py`) with a two-frame loop that switches every 0.5 seconds while jobs are executing.
- Added packaged config-template resources under `outlook_mail_extractor/resources/config_samples/**` and runtime seeding utilities (`config_templates.py`) so `uv tool` installs can initialize config files without relying on repository-local `config/` files.
- Added a dedicated TUI entrypoint module (`outlook_mail_extractor/tui.py`) and script command `mailslide-tui` for tool-install execution (`uv tool install mailslide` + `mailslide-tui`).
- Added release automation/docs artifacts for PyPI-first distribution, including `scripts/release_pypi.ps1`, `tasks/release_checklist_pypi.md`, and `MANIFEST.in` (`prune tests`) to keep source distributions lean.
- Added job-execution path-normalization tests and service coverage (`tests/test_job_execution_service.py`) for plugin output-path resolution behavior.
- Added plugin-editor path-resolution tests in `tests/test_plugin_config_editor.py` to cover absolute-path rendering for `path` fields with/without runtime base directory context.
- Added Windows DPAPI-backed secret storage for `llm-config` API keys via `outlook_mail_extractor/secrets.py`, writing encrypted key material to `config/llm-api-key.bin` instead of plaintext YAML.
- Added PyPI-based app update checks (`outlook_mail_extractor/services/update_check.py`) with startup delayed-check behavior (20s), plus About-tab update status display and a manual "Check Updates" action.
- Added config-schema migration scaffolding (`outlook_mail_extractor/config_migration.py`) so legacy configs are upgraded in-place (`v0 -> v2`) with timestamped backups and `jobs[].batch_flush_enabled` default backfill.

### Changed

- Changed runtime path defaults for packaged/tool mode to user data directories (via `platformdirs`, with `MAILSLIDE_DATA_DIR` override), while preserving repo-root behavior for explicit source-mode runtime contexts.
- Changed CLI default `--config` path resolution to use runtime context (`runtime.paths.config_file`) instead of hardcoded `config/config.yaml`.
- Changed docs (`README*`, `GUIDE*`, task plans/checklists) to make PyPI/`uv tool` the primary distribution path and de-emphasize GitHub Releases as a release channel.
- Changed About-tab `Initialize Config` feedback to use Textual `notify(...)` toast messages instead of inline status replacement, so users can reliably see setup results.
- Changed Home-tab `Preserve RE/FW` toggle default to `ON` (while keeping the existing one-click toggle behavior) so first-run execution preserves reply/forward context by default.
- Changed docs (`README*`, `GUIDE*`) to explicitly document Home `Preserve RE/FW` default-on behavior.
- Changed README language filenames so English is now `README.md` and Traditional Chinese is `README.zh-TW.md` (previously `README.en.md` and `README.md`).
- Changed LLM config save/load flow to keep `api_key` blank in `config/llm-config.yaml`, transparently loading from DPAPI secret storage when available and scrubbing legacy plaintext keys before backup writes.
- Changed update notifications to use `notify(...)` when newer PyPI stable versions are detected, guiding users to upgrade with `uv tool upgrade mailslide`.
- Changed `load_config` to auto-run config migration before validation and persist `config_version` back to `config/config.yaml` after successful migration.

### Fixed

- Fixed Home-tab run animation alignment/rendering so the ASCII block is right-aligned as a single block (without shifting the jobs table) and literal `[@]` characters render correctly instead of being interpreted as Rich markup.
- Fixed plugin output-file discoverability in `uv tool` runtime by resolving relative `output_dir` / `output_file` values against the active config directory (not process CWD), preventing writes to unexpected locations.
- Fixed plugin success observability for writable outputs by attaching output path details to `summary_file` / `event_table` success results.
- Fixed first-run initialization UX by adding an explicit restart reminder toast after creating config files from About > Initialize Config.
- Fixed plugin-config editor path-field clarity by converting relative `output_dir` / `output_file` values to absolute paths (based on active `config` directory) before editing/saving, so users can see and persist exact output locations.

## [v0.3.5] - 2026-03-27

### Changed

- Updated both README language variants (`README.md`, `README.en.md`) with a clear AI-processing warning to avoid sending emails containing personal privacy data or business confidential information.
- Updated both README language variants to explicitly recommend using local models when handling sensitive emails.
- Added an explicit disclaimer in both README files stating that the project is provided as-is and project authors are not liable for data breaches or confidential information leakage caused by user inputs or model services.
- Updated i18n default behavior to use `en-US` as the base language while auto-detecting Windows UI locale on first run; when locale resolves to Traditional Chinese, the app now defaults to `zh-TW` if no explicit/configured language is set.
- Updated plugin config examples to English-first content across built-in plugin samples (`add_category`, `move_to_folder`, `create_appointment`, `event_table`, `summary_file`, `write_file`), including system prompts, profile descriptions, JSON example values, and `_ui` labels/messages.
- Updated language-sensitive tests to accept bilingual validation messages where applicable and added coverage for first-run system-language fallback in TUI language initialization.

## [v0.3.4] - 2026-03-27

### Changed

- Updated `event_table` Excel schema field name from `outlook_link` to `outlook_open_command`, and changed output behavior from clickable deep links/launcher files to plain PowerShell open commands for better compatibility in locked-down environments.
- Updated `event_table` open-command generation to use PowerShell `-EncodedCommand` and robust Outlook COM search logic based on subject/received time traversal across stores/folders instead of relying on unstable `EntryID`/protocol handlers.
- Updated default open-command matching window to subject + received time (within 1 day) and added optional sender matching control.

### Added

- Added `open_command_match_sender` plugin config (and `_ui` schema field) for `event_table` so users can optionally require sender matching when resolving mails from `outlook_open_command`.
- Added `EmailDTO.store_id` and `EmailDTO.internet_message_id` extraction plumbing in core email extraction to support cross-store identification and future fallback matching strategies.
- Added/updated `event_table` tests to cover encoded PowerShell command output and sender-match toggle behavior.

## [v0.3.3] - 2026-03-27

### Fixed

- Fixed Home/Job execution logs so runtime messages now follow the selected UI language (`ui_language`) instead of staying hardcoded in Traditional Chinese.

### Changed

- Migrated job-run related log messages to i18n keys across runtime modules (`job_execution`, `core`, `llm_dispatcher`, `logger`) and added matching `zh-TW`/`en-US` locale entries.
- Updated i18n test expectations in `tests/test_i18n.py` to align with current app branding/copy (`app.title`, `app.subtitle`).

### Added

- Added `tests/test_job_log_i18n.py` regression coverage to verify log message localization changes when switching between `zh-TW` and `en-US`.

## [v0.3.2] - 2026-03-26

### Changed

- Renamed project/package distribution branding from `outlook-mail-extractor` to `mailslide` in package metadata, UI title strings, and README documents.
- Replaced CLI command references with `mailslide` and removed the legacy `outlook-extract` script entry from packaging.
- Updated About screen repository URL to `https://github.com/linax777/mailslide`.
- Added Phase 1 import-path compatibility by introducing `mailslide` package re-exports while keeping `outlook_mail_extractor` available during migration.

### Licensing

- Declared package licensing metadata as `GPL-3.0-or-later` and updated user-facing license text to match the existing GPLv3 license file.

## [v0.3.1] - 2026-03-26

### Added

- Added Phase 1 architecture split modules: `outlook_mail_extractor/llm_dispatcher.py`, `outlook_mail_extractor/plugin_runner.py`, and `outlook_mail_extractor/move_policy.py` to isolate LLM dispatch, plugin execution normalization/error wrapping, and move-target policy decisions.
- Added plugin lifecycle hooks (`begin_job` / `end_job`) to support job-scoped buffering and flush workflows for writable plugins.
- Added optional parser-level HTML artifact reuse (`parse_email_html(..., use_cache=True)`) so body extraction and table parsing can share one HTML parse per email.
- Added metrics logging payloads for observability: per-mail summary (`METRIC mail_summary`) and per-job summaries (`METRIC job_summary`, `METRIC job_execution`) including elapsed time, LLM call counts, and plugin status distributions.
- Added UI schema evaluator registry APIs (`register_rule_evaluator`, `get_rule_evaluator`, `list_rule_evaluators`) to support extensible rule wiring without editing the core evaluator map.
- Added optional dynamic plugin discovery support via top-level config `plugin_modules` (runtime import for custom plugin modules).
- Added new tests for Phase 1/2 behavior, including `tests/test_llm_dispatcher.py`, `tests/test_plugin_runner.py`, `tests/test_move_policy.py`, parser HTML parse bundle coverage, plugin batch-flush workflows, and runtime rule-registry registration.

### Changed

- Refactored `EmailProcessor` orchestration to call shared dispatch/execution/policy helpers instead of duplicating shared/per-plugin/no-LLM branches, while preserving existing external behavior.
- Updated `EmailProcessor.extract_email_data` to parse HTML once and reuse parsed artifacts for cleaned body and table extraction.
- Updated `event_table` and `summary_file` output strategy from immediate per-mail writes to default job-level batch flush (configurable per job with `batch_flush_enabled`, default `true`, with fallback switch-off support).
- Updated changelog/version consistency by aligning package `__version__` with `pyproject.toml` and documenting current config/runtime knobs in samples and README.
- Updated workspace hygiene by ignoring `*.bak` files to reduce backup-noise in local working trees.

## [v0.3.0] - 2026-03-24

### Added

- Added English documentation file `README.en.md` with installation, TUI/CLI usage, configuration examples, plugin overview, localization notes, and local `llama.cpp` setup.
- Added cross-language navigation links at the top of both README files (`README.md` <-> `README.en.md`) so users can switch languages quickly.
- Added usage-screen tests in `tests/test_usage_screen.py` to verify language-based README resolution and fallback behavior.
- Added key-based i18n runtime (`outlook_mail_extractor/i18n.py`) with gettext catalog loading and YAML fallback dictionaries for `zh-TW` and `en-US`.
- Added CLI language override `--lang` (`zh-TW`/`en-US`) and config-level `ui_language` support in `config/config.yaml(.sample)`.
- Added Language modal in TUI (hotkey `L`) with radio-button selection, persisted language updates to `config/config.yaml`, and immediate UI recompose on language switch.
- Added Babel i18n tooling (`babel.cfg`, locale `pot/po` files, `scripts/i18n.ps1`) and README instructions for extract/init/update/compile workflows.
- Added i18n/config tests (`tests/test_i18n.py`, `tests/test_config_ui_language.py`, `tests/test_app_language.py`) and extended schema tests for `label_key`/`message_key` support.

### Changed

- Migrated major TUI/CLI surfaces to translation keys, including app shell/tab labels, Home/About/Schedule/Usage pages, Configuration tabs, Main Config workflows, and key modal/error notifications.
- Updated `_ui` schema handling to support localized key fields (`label_key`, `message_key`) with backward-compatible fallback to raw `label`/`message` text.
- Updated Plugin/Main config editor rendering and rule evaluation paths to resolve translated schema labels/messages at runtime.
- Updated packaging metadata to include locale resources and Babel dev dependency.
- Updated Guide tab content loading (`outlook_mail_extractor/screens/usage.py`) to read README by active app language: `en-US` prefers `README.en.md` with fallback to `README.md`, while `zh-TW` continues using `README.md`.

## [v0.2.8] - 2026-03-24

### Added

- Added per-job `manual_review_destination` routing support so emails with no LLM action outcome are moved to a dedicated manual-review folder.
- Added high-risk core tests to cover move routing for LLM success -> `destination`, non-action -> `manual_review_destination`, and plugin failure -> `manual_review_destination`.
- Added a new `修改 Job` action in Main Configuration `_ui` schema so users can update existing jobs from the form-driven workflow instead of editing YAML manually.
- Added modal/form test coverage for job edit helpers and add/edit payload handling, including `manual_review_destination` field mapping.

### Changed

- Updated orchestrator move logic to route mails based on LLM plugin result statuses: `SUCCESS` goes to `destination`, while `SKIPPED`/`FAILED`/`RETRIABLE_FAILED` can be routed to `manual_review_destination`.
- Updated config sample/UI schema and README job fields to document and expose `manual_review_destination` in TUI and YAML workflows.
- Updated Main Configuration tab to support editing the selected job through a dedicated modal, reusing the structured job form fields (`name/account/source/destination/manual_review_destination/limit/plugins`) and reducing direct YAML edits.

## [v0.2.7] - 2026-03-24

### Changed

- Updated `event_table` output from CSV to Excel (`.xlsx`) and changed default output path to `output/events.xlsx`.
- Updated `event_table` fixed schema to include Outlook message identifiers and deep-link fields: `email_entry_id` and `outlook_link`.
- Updated `config/plugins/event_table.yaml(.sample)` UI schema and validation rule from `.csv` to `.xlsx` output checks.
- Updated README plugin documentation for the new Excel-based event table workflow and Outlook classic open-link behavior.

### Added

- Added `EmailDTO.entry_id` and wired message extraction to include Outlook `EntryID` in core processing.
- Added Excel hyperlink writing in `event_table` so each row includes a clickable `outlook:<EntryID>` link (`Open in Outlook`) for opening the matching mail in Outlook classic.
- Added `openpyxl` runtime dependency and lockfile update for Excel read/write support.
- Added/updated tests covering Excel output headers/rows, hyperlink generation, append behavior, timezone datetime parsing, and UI schema rule support for `output_file_xlsx`.

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
