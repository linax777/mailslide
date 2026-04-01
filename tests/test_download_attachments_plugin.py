import asyncio
from pathlib import Path

import pytest

from outlook_mail_extractor.adapters.outlook_actions import OutlookMailActionAdapter
from outlook_mail_extractor.models import (
    AttachmentDescriptor,
    EmailDTO,
    PluginExecutionResult,
    PluginExecutionStatus,
)
from outlook_mail_extractor.plugins.download_attachments import (
    DownloadAttachmentsPlugin,
)


_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"
_PR_ATTACHMENT_HIDDEN = "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B"


class _FakePropertyAccessor:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self._values = values or {}

    def GetProperty(self, property_name: str) -> object:
        if property_name not in self._values:
            raise RuntimeError("missing property")
        return self._values[property_name]


class _FakeAttachment:
    def __init__(
        self,
        filename: str,
        *,
        attachment_type: int | None = 1,
        hidden: bool | None = None,
        content_id: str = "",
        save_error: Exception | None = None,
    ) -> None:
        self.FileName = filename
        self.Type = attachment_type
        props: dict[str, object] = {}
        if hidden is not None:
            props[_PR_ATTACHMENT_HIDDEN] = hidden
        if content_id:
            props[_PR_ATTACH_CONTENT_ID] = content_id
        self.PropertyAccessor = _FakePropertyAccessor(props)
        self._save_error = save_error

    def SaveAsFile(self, destination_path: str) -> None:
        if self._save_error is not None:
            raise self._save_error
        Path(destination_path).write_text("saved", encoding="utf-8")


class _FakeAttachmentsCollection:
    def __init__(self, attachments: list[_FakeAttachment]) -> None:
        self._attachments = attachments
        self.Count = len(attachments)

    def Item(self, index: int) -> _FakeAttachment:
        return self._attachments[index - 1]


class _FakeMessage:
    def __init__(self, attachments: list[_FakeAttachment]) -> None:
        self.Attachments = _FakeAttachmentsCollection(attachments)


class _RecordingActionPort:
    def __init__(
        self,
        descriptors: list[AttachmentDescriptor],
        save_errors: dict[int, Exception] | None = None,
    ) -> None:
        self._descriptors = descriptors
        self._save_errors = save_errors or {}
        self.saved_paths: list[Path] = []

    def move_to_folder(self, folder_name: str, create_if_missing: bool = True) -> None:
        del folder_name
        del create_if_missing

    def add_categories(self, categories: list[str]) -> None:
        del categories

    def create_appointment(self, *args, **kwargs) -> None:
        del args
        del kwargs

    def list_attachments(self) -> list[AttachmentDescriptor]:
        return list(self._descriptors)

    def save_attachment(self, attachment_index: int, destination_path: Path) -> None:
        error = self._save_errors.get(attachment_index)
        if error is not None:
            raise error
        destination_path.write_text("payload", encoding="utf-8")
        self.saved_paths.append(destination_path)


def _build_email(entry_id: str = "entry-1") -> EmailDTO:
    return EmailDTO(
        subject="Invoice",
        sender="sender@example.com",
        received="2026-04-01 08:00:00",
        body="Body",
        tables=[],
        entry_id=entry_id,
    )


def _build_plugin(output_dir: Path) -> DownloadAttachmentsPlugin:
    plugin = DownloadAttachmentsPlugin(config={"output_dir": str(output_dir)})
    plugin.begin_job({"job_name": "Billing Job"})
    return plugin


def test_outlook_adapter_lists_attachments_with_strong_signal_fields() -> None:
    message = _FakeMessage(
        [
            _FakeAttachment("A.pdf", hidden=False),
            _FakeAttachment(
                "B.msg", hidden=True, attachment_type=5, content_id="cid:b"
            ),
        ]
    )
    adapter = OutlookMailActionAdapter(
        client=object(), message=message, account_name="x"
    )

    descriptors = adapter.list_attachments()

    assert [descriptor.index for descriptor in descriptors] == [1, 2]
    assert descriptors[0].hidden is False
    assert descriptors[0].embedded_item_type is False
    assert descriptors[1].hidden is True
    assert descriptors[1].embedded_item_type is True
    assert descriptors[1].has_content_id is True


def test_outlook_adapter_descriptor_keeps_missing_filename() -> None:
    message = _FakeMessage([_FakeAttachment("", attachment_type=None)])
    adapter = OutlookMailActionAdapter(
        client=object(), message=message, account_name="x"
    )

    descriptors = adapter.list_attachments()

    assert descriptors[0].filename == ""
    assert descriptors[0].metadata_complete is False


def test_outlook_adapter_save_attachment_propagates_error() -> None:
    message = _FakeMessage(
        [_FakeAttachment("A.pdf", save_error=PermissionError("denied"))]
    )
    adapter = OutlookMailActionAdapter(
        client=object(), message=message, account_name="x"
    )

    with pytest.raises(PermissionError, match="denied"):
        adapter.save_attachment(1, Path("attachment.pdf"))


def test_download_attachments_skips_when_two_strong_inline_signals(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    action_port = _RecordingActionPort(
        [
            AttachmentDescriptor(
                index=1,
                filename="image001.png",
                has_content_id=True,
                hidden=True,
                embedded_item_type=False,
            )
        ]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert result.status == PluginExecutionStatus.SKIPPED
    email_detail = result.details["emails"][0]
    assert email_detail["downloaded_count"] == 0
    assert email_detail["skipped_inline_reasons"] == {
        "high_confidence_inline_content_id_hidden": 1
    }


def test_download_attachments_downloads_when_no_strong_inline_signals(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    action_port = _RecordingActionPort(
        [AttachmentDescriptor(index=1, filename="invoice.pdf")]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert isinstance(result, PluginExecutionResult)
    assert result.status == PluginExecutionStatus.SUCCESS
    email_detail = result.details["emails"][0]
    assert email_detail["saved_relative_paths"] == ["invoice.pdf"]
    assert email_detail["skipped_inline_reasons"] == {}


def test_download_attachments_one_strong_signal_downloads_with_fallback_count(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    action_port = _RecordingActionPort(
        [
            AttachmentDescriptor(
                index=1,
                filename="note.txt",
                has_content_id=True,
                hidden=False,
                embedded_item_type=False,
                metadata_complete=True,
            )
        ]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert result.status == PluginExecutionStatus.SUCCESS
    assert result.details["emails"][0]["inline_fallback_count"] == 1


def test_download_attachments_conflicting_metadata_uses_two_signal_rule(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    action_port = _RecordingActionPort(
        [
            AttachmentDescriptor(
                index=1,
                filename="report.docx",
                has_content_id=False,
                hidden=False,
                embedded_item_type=True,
                metadata_complete=True,
            )
        ]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert result.status == PluginExecutionStatus.SUCCESS
    assert result.details["emails"][0]["downloaded_count"] == 1


def test_download_attachments_metadata_inconclusive_counts_fallback(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    action_port = _RecordingActionPort(
        [
            AttachmentDescriptor(
                index=1,
                filename="details.txt",
                metadata_complete=False,
            )
        ]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert result.status == PluginExecutionStatus.SUCCESS
    assert result.details["emails"][0]["inline_fallback_count"] == 1


def test_download_attachments_maps_directory_create_failure_to_runtime_code(
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "blocked.txt"
    blocked.write_text("x", encoding="utf-8")
    plugin = _build_plugin(blocked)
    action_port = _RecordingActionPort(
        [AttachmentDescriptor(index=1, filename="a.pdf")]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert result.status == PluginExecutionStatus.FAILED
    assert result.code == "runtime_output_dir_unwritable"
    assert result.details["run_code"] == "runtime_output_dir_unwritable"


def test_download_attachments_maps_invalid_filename_after_sanitize(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    action_port = _RecordingActionPort(
        [AttachmentDescriptor(index=1, filename="...", metadata_complete=True)]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert result.status == PluginExecutionStatus.FAILED
    failure = result.details["emails"][0]["failed_files"][0]
    assert failure["code"] == "invalid_attachment_name"


def test_download_attachments_saved_relative_paths_follow_index_order(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    action_port = _RecordingActionPort(
        [
            AttachmentDescriptor(index=1, filename="Report.pdf"),
            AttachmentDescriptor(index=2, filename="Report.pdf"),
            AttachmentDescriptor(index=3, filename="Report.pdf"),
        ]
    )

    result = asyncio.run(plugin.execute(_build_email(), "", action_port))

    assert result.status == PluginExecutionStatus.SUCCESS
    email_detail = result.details["emails"][0]
    assert email_detail["saved_relative_paths"] == [
        "Report.pdf",
        "Report (1).pdf",
        "Report (2).pdf",
    ]


def test_download_attachments_runtime_failure_code_precedence_across_run(
    tmp_path: Path,
) -> None:
    plugin = _build_plugin(tmp_path)
    save_failure_result = asyncio.run(
        plugin.execute(
            _build_email(entry_id="entry-1"),
            "",
            _RecordingActionPort(
                [AttachmentDescriptor(index=1, filename="invoice.pdf")],
                save_errors={1: OSError("disk full")},
            ),
        )
    )

    blocked = tmp_path / "blocked.txt"
    blocked.write_text("x", encoding="utf-8")
    plugin.output_dir = str(blocked)
    dir_failure_result = asyncio.run(
        plugin.execute(
            _build_email(entry_id="entry-2"),
            "",
            _RecordingActionPort([AttachmentDescriptor(index=1, filename="b.pdf")]),
        )
    )

    assert save_failure_result.code == "runtime_attachment_download_failed"
    assert dir_failure_result.code == "runtime_output_dir_unwritable"
    assert dir_failure_result.details["run_code"] == "runtime_output_dir_unwritable"
