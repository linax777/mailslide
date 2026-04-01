from pathlib import Path

from outlook_mail_extractor.plugins.download_attachments_paths import (
    build_collision_index,
    build_job_folder_key,
    plan_attachment_path,
    sanitize_attachment_filename,
)


def test_build_job_folder_key_is_deterministic() -> None:
    key_a = build_job_folder_key("Monthly Billing")
    key_b = build_job_folder_key("Monthly Billing")

    assert key_a == key_b
    assert key_a.startswith("Monthly Billing-")
    assert len(key_a.rsplit("-", maxsplit=1)[-1]) == 8


def test_sanitize_attachment_filename_handles_reserved_and_trailing_chars() -> None:
    assert sanitize_attachment_filename("CON.txt") == "_CON.txt"
    assert sanitize_attachment_filename("summary. ") == "summary"


def test_plan_attachment_path_handles_unicode_equivalent_conflicts(
    tmp_path: Path,
) -> None:
    existing_name = "Cafe\u0301.pdf"
    (tmp_path / existing_name).write_text("x", encoding="utf-8")

    index = build_collision_index([path.name for path in tmp_path.iterdir()])
    planned = plan_attachment_path(
        parent_dir=tmp_path,
        source_filename="Caf\u00e9.pdf",
        collision_index=index,
    )

    assert planned.status == "ok"
    assert planned.filename == "Caf\u00e9 (1).pdf"
    assert planned.path == tmp_path / "Caf\u00e9 (1).pdf"


def test_plan_attachment_path_returns_path_too_long_after_secondary_retry(
    tmp_path: Path,
) -> None:
    index = build_collision_index([])
    deep_parent = tmp_path / ("segment" * 20)

    planned = plan_attachment_path(
        parent_dir=deep_parent,
        source_filename="report.pdf",
        collision_index=index,
        full_path_budget=len(str(deep_parent)) + 1,
    )

    assert planned.status == "path_too_long"
    assert planned.path is None


def test_plan_attachment_path_allocates_deterministic_conflict_suffix(
    tmp_path: Path,
) -> None:
    (tmp_path / "Report.pdf").write_text("a", encoding="utf-8")
    (tmp_path / "report.pdf").write_text("b", encoding="utf-8")
    (tmp_path / "Report (1).pdf").write_text("c", encoding="utf-8")

    index = build_collision_index([path.name for path in tmp_path.iterdir()])
    planned = plan_attachment_path(
        parent_dir=tmp_path,
        source_filename="Report.pdf",
        collision_index=index,
    )

    assert planned.status == "ok"
    assert planned.filename == "Report (2).pdf"
