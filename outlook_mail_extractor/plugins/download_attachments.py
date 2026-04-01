"""Download regular Outlook attachments to deterministic per-job folders."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from ..models import (
    AttachmentDescriptor,
    EmailDTO,
    MailActionPort,
    PluginExecutionResult,
)
from .base import BasePlugin, PluginConfig, register_plugin
from .download_attachments_paths import (
    DEFAULT_FILENAME_MAX_LENGTH,
    DEFAULT_FULL_PATH_BUDGET,
    DEFAULT_JOB_FOLDER_MAX_LENGTH,
    CollisionIndex,
    build_collision_index,
    build_job_folder_key,
    plan_attachment_path,
)

_FILE_CODE_DIR_CREATE_FAILED = "dir_create_failed"
_FILE_CODE_DIR_NOT_WRITABLE = "dir_not_writable"
_FILE_CODE_INVALID_ATTACHMENT_NAME = "invalid_attachment_name"
_FILE_CODE_PATH_TOO_LONG = "path_too_long"
_FILE_CODE_SAVE_FAILED = "save_failed"
_FILE_CODE_UNKNOWN_WRITE_ERROR = "unknown_write_error"

_TOP_CODE_STARTUP_OUTPUT_DIR_INVALID = "startup_output_dir_invalid"
_TOP_CODE_RUNTIME_OUTPUT_DIR_UNWRITABLE = "runtime_output_dir_unwritable"
_TOP_CODE_RUNTIME_ATTACHMENT_DOWNLOAD_FAILED = "runtime_attachment_download_failed"

_SKIP_REASON_CONTENT_ID_HIDDEN = "high_confidence_inline_content_id_hidden"
_SKIP_REASON_CONTENT_ID_EMBEDDED = "high_confidence_inline_content_id_embedded"
_SKIP_REASON_HIDDEN_EMBEDDED = "high_confidence_inline_hidden_embedded"


@register_plugin
class DownloadAttachmentsPlugin(BasePlugin):
    """Download regular attachments into deterministic per-job output folders."""

    name = "download_attachments"
    default_system_prompt = ""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = self._load_config(config)
        self.output_dir = str(config.get("output_dir", "")).strip()
        self.job_folder_max_length = self._coerce_positive_int(
            config.get("job_folder_max_length", DEFAULT_JOB_FOLDER_MAX_LENGTH),
            default=DEFAULT_JOB_FOLDER_MAX_LENGTH,
        )
        self.filename_max_length = self._coerce_positive_int(
            config.get("filename_max_length", DEFAULT_FILENAME_MAX_LENGTH),
            default=DEFAULT_FILENAME_MAX_LENGTH,
        )
        self.full_path_budget = self._coerce_positive_int(
            config.get("full_path_budget", DEFAULT_FULL_PATH_BUDGET),
            default=DEFAULT_FULL_PATH_BUDGET,
        )

        self._job_name = "job"
        self._job_folder_key = build_job_folder_key(
            self._job_name,
            max_length=self.job_folder_max_length,
        )
        self._collision_indexes: dict[str, CollisionIndex] = {}
        self._run_statuses: list[str] = []
        self._run_failure_codes: set[str] = set()

    def _load_config(self, config: dict) -> PluginConfig:
        return PluginConfig(
            enabled=config.get("enabled", True),
            system_prompt=config.get("system_prompt", self.default_system_prompt),
            response_format=config.get("response_format", "json"),
            override_prompt=config.get("override_prompt"),
            response_json_format=config.get("response_json_format"),
        )

    def begin_job(self, context: dict | None = None) -> None:
        context = context or {}
        raw_job_name = str(context.get("job_name", "")).strip()
        self._job_name = raw_job_name or "job"
        self._job_folder_key = build_job_folder_key(
            self._job_name,
            max_length=self.job_folder_max_length,
        )
        self._collision_indexes = {}
        self._run_statuses = []
        self._run_failure_codes = set()

    async def execute(
        self,
        email_data: EmailDTO,
        llm_response: str,
        action_port: MailActionPort,
    ) -> PluginExecutionResult:
        """Download non-inline attachments for one email."""
        del llm_response

        if not self.output_dir:
            return self._finalize_result(
                email_data=email_data,
                email_status="failed",
                email_code=_TOP_CODE_STARTUP_OUTPUT_DIR_INVALID,
                message="Missing output_dir",
                downloaded_count=0,
                inline_fallback_count=0,
                skipped_inline_reasons={},
                failed_files=[
                    self._build_failed_file(
                        source_attachment_name="",
                        code=_FILE_CODE_DIR_CREATE_FAILED,
                        message="Plugin output_dir is not configured",
                    )
                ],
                job_output_dir="",
                saved_relative_paths=[],
                saved_files=[],
            )

        job_output_dir = Path(self.output_dir).expanduser() / self._job_folder_key

        try:
            descriptors = sorted(
                action_port.list_attachments(),
                key=lambda descriptor: descriptor.index,
            )
        except Exception as error:
            return self._finalize_result(
                email_data=email_data,
                email_status="failed",
                email_code=_TOP_CODE_RUNTIME_ATTACHMENT_DOWNLOAD_FAILED,
                message="Failed to list attachments",
                downloaded_count=0,
                inline_fallback_count=0,
                skipped_inline_reasons={},
                failed_files=[
                    self._build_failed_file(
                        source_attachment_name="",
                        code=_FILE_CODE_UNKNOWN_WRITE_ERROR,
                        message=f"List attachments failed: {error}",
                    )
                ],
                job_output_dir=str(job_output_dir),
                saved_relative_paths=[],
                saved_files=[],
            )

        downloaded_count = 0
        inline_fallback_count = 0
        skipped_inline_reasons: dict[str, int] = {}
        failed_files: list[dict[str, str]] = []
        saved_relative_paths: list[str] = []
        saved_files: list[dict[str, str]] = []

        output_ready = False
        runtime_output_dir_failure = False

        for descriptor in descriptors:
            should_skip, reason_code, fallback_download = self._evaluate_inline_skip(
                descriptor
            )
            if should_skip:
                if isinstance(reason_code, str):
                    skipped_inline_reasons[reason_code] = (
                        skipped_inline_reasons.get(reason_code, 0) + 1
                    )
                continue

            if fallback_download:
                inline_fallback_count += 1

            source_name = str(descriptor.filename).strip()
            if not source_name:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name="",
                        code=_FILE_CODE_INVALID_ATTACHMENT_NAME,
                        message="Attachment filename is empty",
                    )
                )
                continue

            if not output_ready:
                output_ready, output_error_code, output_error_message = (
                    self._prepare_output_directory(job_output_dir)
                )
                if not output_ready:
                    runtime_output_dir_failure = True
                    failed_files.append(
                        self._build_failed_file(
                            source_attachment_name=source_name,
                            code=output_error_code,
                            message=output_error_message,
                        )
                    )
                    break

            collision_index = self._get_collision_index(job_output_dir)
            planned_path = plan_attachment_path(
                parent_dir=job_output_dir,
                source_filename=source_name,
                collision_index=collision_index,
                filename_max_length=self.filename_max_length,
                full_path_budget=self.full_path_budget,
            )

            if planned_path.status == _FILE_CODE_INVALID_ATTACHMENT_NAME:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FILE_CODE_INVALID_ATTACHMENT_NAME,
                        message="Attachment filename is invalid after sanitization",
                    )
                )
                continue

            if planned_path.status != "ok" or planned_path.path is None:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FILE_CODE_PATH_TOO_LONG,
                        message=(
                            "Attachment path exceeds deterministic path budget "
                            f"({self.full_path_budget})"
                        ),
                    )
                )
                continue

            try:
                action_port.save_attachment(descriptor.index, planned_path.path)
            except PermissionError as error:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FILE_CODE_SAVE_FAILED,
                        message=f"Save failed: {error}",
                    )
                )
                continue
            except OSError as error:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FILE_CODE_SAVE_FAILED,
                        message=f"Save failed: {error}",
                    )
                )
                continue
            except Exception as error:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FILE_CODE_UNKNOWN_WRITE_ERROR,
                        message=f"Save failed: {error}",
                    )
                )
                continue

            downloaded_count += 1
            relative_path = self._to_relative_output_path(
                job_output_dir, planned_path.path
            )
            saved_relative_paths.append(relative_path)
            saved_files.append(
                {
                    "source_attachment_name": source_name,
                    "saved_filename": planned_path.filename,
                    "saved_relative_path": relative_path,
                    "saved_path": str(planned_path.path),
                }
            )

        if failed_files:
            email_code = (
                _TOP_CODE_RUNTIME_OUTPUT_DIR_UNWRITABLE
                if runtime_output_dir_failure
                else _TOP_CODE_RUNTIME_ATTACHMENT_DOWNLOAD_FAILED
            )
            return self._finalize_result(
                email_data=email_data,
                email_status="failed",
                email_code=email_code,
                message="Attachment download failed for one or more files",
                downloaded_count=downloaded_count,
                inline_fallback_count=inline_fallback_count,
                skipped_inline_reasons=skipped_inline_reasons,
                failed_files=failed_files,
                job_output_dir=str(job_output_dir),
                saved_relative_paths=saved_relative_paths,
                saved_files=saved_files,
            )

        if downloaded_count > 0:
            return self._finalize_result(
                email_data=email_data,
                email_status="success",
                email_code="downloaded",
                message="Attachments downloaded",
                downloaded_count=downloaded_count,
                inline_fallback_count=inline_fallback_count,
                skipped_inline_reasons=skipped_inline_reasons,
                failed_files=[],
                job_output_dir=str(job_output_dir),
                saved_relative_paths=saved_relative_paths,
                saved_files=saved_files,
            )

        return self._finalize_result(
            email_data=email_data,
            email_status="skipped",
            email_code="no_downloadable_attachments",
            message="No downloadable attachments",
            downloaded_count=0,
            inline_fallback_count=inline_fallback_count,
            skipped_inline_reasons=skipped_inline_reasons,
            failed_files=[],
            job_output_dir=str(job_output_dir),
            saved_relative_paths=[],
            saved_files=[],
        )

    def _prepare_output_directory(self, output_dir: Path) -> tuple[bool, str, str]:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as error:
            return (
                False,
                _FILE_CODE_DIR_CREATE_FAILED,
                f"Cannot create output directory: {error}",
            )

        if not output_dir.is_dir():
            return (
                False,
                _FILE_CODE_DIR_CREATE_FAILED,
                "Configured output path is not a directory",
            )

        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=output_dir,
                delete=True,
                prefix=".mailslide-write-check-",
            ) as probe_file:
                probe_file.write(b"ok")
        except Exception as error:
            return (
                False,
                _FILE_CODE_DIR_NOT_WRITABLE,
                f"Output directory is not writable: {error}",
            )

        return True, "", ""

    def _get_collision_index(self, output_dir: Path) -> CollisionIndex:
        cache_key = str(output_dir)
        cached = self._collision_indexes.get(cache_key)
        if cached is not None:
            return cached

        existing_names: list[str] = []
        if output_dir.exists():
            existing_names = [
                child.name for child in output_dir.iterdir() if child.is_file()
            ]

        index = build_collision_index(existing_names)
        self._collision_indexes[cache_key] = index
        return index

    def _evaluate_inline_skip(
        self, descriptor: AttachmentDescriptor
    ) -> tuple[bool, str | None, bool]:
        signal_has_content_id = bool(descriptor.has_content_id)
        signal_hidden = descriptor.hidden is True
        signal_embedded = bool(descriptor.embedded_item_type)

        strong_signal_count = sum(
            [signal_has_content_id, signal_hidden, signal_embedded]
        )
        if strong_signal_count >= 2:
            return (
                True,
                self._build_inline_skip_reason(
                    signal_has_content_id=signal_has_content_id,
                    signal_hidden=signal_hidden,
                    signal_embedded=signal_embedded,
                ),
                False,
            )

        fallback_download = strong_signal_count == 1 or not descriptor.metadata_complete
        return False, None, fallback_download

    @staticmethod
    def _build_inline_skip_reason(
        *,
        signal_has_content_id: bool,
        signal_hidden: bool,
        signal_embedded: bool,
    ) -> str:
        if signal_has_content_id and signal_hidden:
            return _SKIP_REASON_CONTENT_ID_HIDDEN
        if signal_has_content_id and signal_embedded:
            return _SKIP_REASON_CONTENT_ID_EMBEDDED
        if signal_hidden and signal_embedded:
            return _SKIP_REASON_HIDDEN_EMBEDDED
        return _SKIP_REASON_CONTENT_ID_HIDDEN

    @staticmethod
    def _coerce_positive_int(value: object, *, default: int) -> int:
        if isinstance(value, bool):
            return default

        if isinstance(value, int):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = int(value.strip())
            except ValueError:
                return default
        else:
            return default

        return parsed if parsed > 0 else default

    @staticmethod
    def _build_failed_file(
        *,
        source_attachment_name: str,
        code: str,
        message: str,
    ) -> dict[str, str]:
        return {
            "source_attachment_name": source_attachment_name,
            "code": code,
            "message": message,
        }

    @staticmethod
    def _to_relative_output_path(job_output_dir: Path, saved_path: Path) -> str:
        relative = saved_path.relative_to(job_output_dir)
        return relative.as_posix()

    def _finalize_result(
        self,
        *,
        email_data: EmailDTO,
        email_status: str,
        email_code: str,
        message: str,
        downloaded_count: int,
        inline_fallback_count: int,
        skipped_inline_reasons: dict[str, int],
        failed_files: list[dict[str, str]],
        job_output_dir: str,
        saved_relative_paths: list[str],
        saved_files: list[dict[str, str]],
    ) -> PluginExecutionResult:
        self._run_statuses.append(email_status)
        if email_status == "failed":
            self._run_failure_codes.add(email_code)

        run_status = self._aggregate_run_status()
        run_code = self._aggregate_run_code(run_status=run_status)
        details = {
            "status": run_status,
            "code": run_code,
            "emails": [
                {
                    "entry_id": str(email_data.entry_id),
                    "status": email_status,
                    "code": email_code,
                    "downloaded_count": downloaded_count,
                    "job_output_dir": job_output_dir,
                    "saved_relative_paths": saved_relative_paths,
                    "inline_fallback_count": inline_fallback_count,
                    "skipped_inline_reasons": skipped_inline_reasons,
                    "failed_files": failed_files,
                    "saved_files": saved_files,
                }
            ],
            "run_status": run_status,
            "run_code": run_code,
        }

        if run_status == "success":
            return self.success_result(message=message, code=run_code, details=details)
        if run_status == "skipped":
            return self.skipped_result(message=message, code=run_code, details=details)
        return self.failed_result(message=message, code=run_code, details=details)

    def _aggregate_run_status(self) -> str:
        if any(status == "failed" for status in self._run_statuses):
            return "failed"
        if any(status == "success" for status in self._run_statuses):
            return "success"
        return "skipped"

    def _aggregate_run_code(self, *, run_status: str) -> str:
        if run_status == "failed":
            if _TOP_CODE_RUNTIME_OUTPUT_DIR_UNWRITABLE in self._run_failure_codes:
                return _TOP_CODE_RUNTIME_OUTPUT_DIR_UNWRITABLE
            return _TOP_CODE_RUNTIME_ATTACHMENT_DOWNLOAD_FAILED

        if run_status == "success":
            return "downloaded"
        return "no_downloadable_attachments"
