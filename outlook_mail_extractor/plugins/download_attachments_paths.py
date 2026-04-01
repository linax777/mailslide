"""Deterministic path utilities for attachment export plugin."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_JOB_FOLDER_MAX_LENGTH = 60
DEFAULT_FILENAME_MAX_LENGTH = 120
DEFAULT_FULL_PATH_BUDGET = 240

_INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


@dataclass
class CollisionIndex:
    """Track allocated names using Unicode-normalized case-insensitive identity."""

    names: set[str]
    identities: set[str]


@dataclass(frozen=True)
class PlannedAttachmentPath:
    """Result for one deterministic attachment path planning attempt."""

    status: str
    filename: str
    path: Path | None
    secondary_truncation_applied: bool = False


def normalize_job_name_for_hash(job_name: str) -> str:
    """Normalize job name for stable folder hash identity."""
    normalized = unicodedata.normalize("NFKC", str(job_name))
    normalized = normalized.casefold()
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    return normalized or "job"


def build_job_folder_key(
    job_name: str,
    *,
    max_length: int = DEFAULT_JOB_FOLDER_MAX_LENGTH,
) -> str:
    """Build deterministic job-folder key `<safe_name>-<sha1_8>`."""
    normalized = normalize_job_name_for_hash(job_name)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]

    if max_length <= len(digest):
        return digest[:max_length]

    base_max = max(1, max_length - len(digest) - 1)
    safe_name = _sanitize_component(
        str(job_name),
        max_length=base_max,
        fallback="job",
        keep_extension=False,
    )
    return f"{safe_name}-{digest}"


def sanitize_attachment_filename(
    filename: str,
    *,
    max_length: int = DEFAULT_FILENAME_MAX_LENGTH,
) -> str:
    """Sanitize one attachment filename with deterministic Windows-safe rules."""
    return _sanitize_component(
        filename,
        max_length=max_length,
        fallback="unnamed",
        keep_extension=True,
    )


def build_collision_index(existing_names: Iterable[str]) -> CollisionIndex:
    """Build normalized case-insensitive collision index from existing filenames."""
    names: set[str] = set()
    identities: set[str] = set()

    for raw_name in existing_names:
        name = str(raw_name).strip()
        if not name:
            continue
        names.add(name)
        identities.add(_collision_identity(name))

    return CollisionIndex(names=names, identities=identities)


def plan_attachment_path(
    *,
    parent_dir: Path,
    source_filename: str,
    collision_index: CollisionIndex,
    filename_max_length: int = DEFAULT_FILENAME_MAX_LENGTH,
    full_path_budget: int = DEFAULT_FULL_PATH_BUDGET,
) -> PlannedAttachmentPath:
    """Plan deterministic filename/path with one path-budget truncation retry."""
    sanitized = sanitize_attachment_filename(
        source_filename,
        max_length=filename_max_length,
    )

    first_candidate = _next_available_name(sanitized, collision_index)
    first_path = parent_dir / first_candidate
    if len(str(first_path)) <= full_path_budget:
        _reserve_name(first_candidate, collision_index)
        return PlannedAttachmentPath(
            status="ok",
            filename=first_candidate,
            path=first_path,
        )

    allowed_filename_length = full_path_budget - len(str(parent_dir)) - 1
    if allowed_filename_length <= 0:
        return PlannedAttachmentPath(
            status="path_too_long",
            filename=first_candidate,
            path=None,
            secondary_truncation_applied=True,
        )

    secondary_base = sanitize_attachment_filename(
        source_filename,
        max_length=allowed_filename_length,
    )
    secondary_candidate = _next_available_name(secondary_base, collision_index)
    secondary_path = parent_dir / secondary_candidate
    if len(str(secondary_path)) <= full_path_budget:
        _reserve_name(secondary_candidate, collision_index)
        return PlannedAttachmentPath(
            status="ok",
            filename=secondary_candidate,
            path=secondary_path,
            secondary_truncation_applied=True,
        )

    return PlannedAttachmentPath(
        status="path_too_long",
        filename=secondary_candidate,
        path=None,
        secondary_truncation_applied=True,
    )


def _sanitize_component(
    raw_name: str,
    *,
    max_length: int,
    fallback: str,
    keep_extension: bool,
) -> str:
    normalized = unicodedata.normalize("NFKC", str(raw_name))
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    normalized = _INVALID_WINDOWS_CHARS.sub("_", normalized)
    normalized = normalized.rstrip(" .")

    candidate = normalized or fallback
    candidate = _protect_reserved_name(candidate, keep_extension=keep_extension)
    candidate = _truncate_name(
        candidate,
        max_length=max(1, int(max_length)),
        keep_extension=keep_extension,
    )
    candidate = candidate.rstrip(" .")
    if not candidate:
        candidate = fallback

    candidate = _protect_reserved_name(candidate, keep_extension=keep_extension)
    return candidate


def _protect_reserved_name(name: str, *, keep_extension: bool) -> str:
    stem, suffix = _split_name(name) if keep_extension else (name, "")
    if stem.upper() in _WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"
    result = f"{stem}{suffix}" if keep_extension else stem
    return result or "_"


def _truncate_name(name: str, *, max_length: int, keep_extension: bool) -> str:
    if len(name) <= max_length:
        return name

    if not keep_extension:
        return name[:max_length]

    stem, suffix = _split_name(name)
    if not suffix:
        return name[:max_length]

    if max_length <= len(suffix):
        return name[:max_length]

    allowed_stem = max(1, max_length - len(suffix))
    return f"{stem[:allowed_stem]}{suffix}"


def _split_name(name: str) -> tuple[str, str]:
    suffix = Path(name).suffix
    if not suffix:
        return name, ""
    stem = name[: -len(suffix)]
    return stem, suffix


def _collision_identity(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(name))
    return normalized.casefold()


def _next_available_name(base_name: str, collision_index: CollisionIndex) -> str:
    if _collision_identity(base_name) not in collision_index.identities:
        return base_name

    stem, suffix = _split_name(base_name)
    candidate_index = 1
    while True:
        candidate = f"{stem} ({candidate_index}){suffix}"
        if _collision_identity(candidate) not in collision_index.identities:
            return candidate
        candidate_index += 1


def _reserve_name(name: str, collision_index: CollisionIndex) -> None:
    collision_index.names.add(name)
    collision_index.identities.add(_collision_identity(name))
