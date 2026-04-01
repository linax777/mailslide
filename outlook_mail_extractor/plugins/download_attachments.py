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

_FAILURE_CODE_DIR_CREATE_FAILED = "dir_create_failed"
_FAILURE_CODE_DIR_NOT_WRITABLE = "dir_not_writable"
_FAILURE_CODE_INVALID_ATTACHMENT_NAME = "invalid_attachment_name"
_FAILURE_CODE_PATH_TOO_LONG = "path_too_long"
_FAILURE_CODE_SAVE_FAILED = "save_failed"
_FAILURE_CODE_UNKNOWN_WRITE_ERROR = "unknown_write_error"


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
                message="Missing output_dir",
                code=_FAILURE_CODE_DIR_CREATE_FAILED,
                downloaded_count=0,
                inline_fallback_count=0,
                failed_files=[
                    self._build_failed_file(
                        source_attachment_name="",
                        code=_FAILURE_CODE_DIR_CREATE_FAILED,
                        message="Plugin output_dir is not configured",
                    )
                ],
                destination_path="",
            )

        job_output_dir = Path(self.output_dir).expanduser() / self._job_folder_key
        destination_path = str(job_output_dir)

        try:
            descriptors = sorted(
                action_port.list_attachments(),
                key=lambda descriptor: descriptor.index,
            )
        except Exception as error:
            return self._finalize_result(
                email_data=email_data,
                email_status="failed",
                message="Failed to list attachments",
                code=_FAILURE_CODE_UNKNOWN_WRITE_ERROR,
                downloaded_count=0,
                inline_fallback_count=0,
                failed_files=[
                    self._build_failed_file(
                        source_attachment_name="",
                        code=_FAILURE_CODE_UNKNOWN_WRITE_ERROR,
                        message=f"List attachments failed: {error}",
                    )
                ],
                destination_path=destination_path,
            )

        downloaded_count = 0
        inline_fallback_count = 0
        failed_files: list[dict[str, str]] = []
        saved_files: list[dict[str, str]] = []
        output_ready = False

        for descriptor in descriptors:
            if self._is_explicit_inline(descriptor):
                continue

            if self._uses_inline_fallback(descriptor):
                inline_fallback_count += 1

            source_name = str(descriptor.filename).strip()
            if not source_name:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name="",
                        code=_FAILURE_CODE_INVALID_ATTACHMENT_NAME,
                        message="Attachment filename is empty",
                    )
                )
                continue

            if not output_ready:
                output_ready, output_error_code, output_error_message = (
                    self._prepare_output_directory(job_output_dir)
                )
                if not output_ready:
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
            if planned_path.status != "ok" or planned_path.path is None:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FAILURE_CODE_PATH_TOO_LONG,
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
                        code=_FAILURE_CODE_SAVE_FAILED,
                        message=f"Save failed: {error}",
                    )
                )
                continue
            except OSError as error:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FAILURE_CODE_SAVE_FAILED,
                        message=f"Save failed: {error}",
                    )
                )
                continue
            except Exception as error:
                failed_files.append(
                    self._build_failed_file(
                        source_attachment_name=source_name,
                        code=_FAILURE_CODE_UNKNOWN_WRITE_ERROR,
                        message=f"Save failed: {error}",
                    )
                )
                continue

            downloaded_count += 1
            saved_files.append(
                {
                    "source_attachment_name": source_name,
                    "saved_filename": planned_path.filename,
                    "saved_path": str(planned_path.path),
                }
            )

        if failed_files:
            return self._finalize_result(
                email_data=email_data,
                email_status="failed",
                message="Attachment download failed for one or more files",
                code="partial_or_full_failure",
                downloaded_count=downloaded_count,
                inline_fallback_count=inline_fallback_count,
                failed_files=failed_files,
                destination_path=destination_path,
                saved_files=saved_files,
            )

        if downloaded_count > 0:
            return self._finalize_result(
                email_data=email_data,
                email_status="success",
                message="Attachments downloaded",
                code="downloaded",
                downloaded_count=downloaded_count,
                inline_fallback_count=inline_fallback_count,
                failed_files=[],
                destination_path=destination_path,
                saved_files=saved_files,
            )

        return self._finalize_result(
            email_data=email_data,
            email_status="skipped",
            message="No downloadable attachments",
            code="no_downloadable_attachments",
            downloaded_count=0,
            inline_fallback_count=inline_fallback_count,
            failed_files=[],
            destination_path=destination_path,
            saved_files=[],
        )

    def _prepare_output_directory(self, output_dir: Path) -> tuple[bool, str, str]:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as error:
            return (
                False,
                _FAILURE_CODE_DIR_CREATE_FAILED,
                f"Cannot create output directory: {error}",
            )

        if not output_dir.is_dir():
            return (
                False,
                _FAILURE_CODE_DIR_CREATE_FAILED,
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
                _FAILURE_CODE_DIR_NOT_WRITABLE,
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

    @staticmethod
    def _is_explicit_inline(descriptor: AttachmentDescriptor) -> bool:
        return bool(descriptor.explicit_inline) or descriptor.has_content_id

    @staticmethod
    def _uses_inline_fallback(descriptor: AttachmentDescriptor) -> bool:
        return descriptor.explicit_inline is None and not descriptor.has_content_id

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

    def _finalize_result(
        self,
        *,
        email_data: EmailDTO,
        email_status: str,
        message: str,
        code: str,
        downloaded_count: int,
        inline_fallback_count: int,
        failed_files: list[dict[str, str]],
        destination_path: str,
        saved_files: list[dict[str, str]] | None = None,
    ) -> PluginExecutionResult:
        self._run_statuses.append(email_status)
        run_status = self._aggregate_run_status()
        details = {
            "emails": [
                {
                    "entry_id": str(email_data.entry_id),
                    "status": email_status,
                    "downloaded_count": downloaded_count,
                    "destination_path": destination_path,
                    "inline_fallback_count": inline_fallback_count,
                    "failed_files": failed_files,
                    "saved_files": saved_files or [],
                }
            ],
            "run_status": run_status,
        }

        if email_status == "success":
            return self.success_result(message=message, code=code, details=details)
        if email_status == "skipped":
            return self.skipped_result(message=message, code=code, details=details)
        return self.failed_result(message=message, code=code, details=details)

    def _aggregate_run_status(self) -> str:
        if any(status == "failed" for status in self._run_statuses):
            return "failed"
        if any(status == "success" for status in self._run_statuses):
            return "success"
        return "skipped"
