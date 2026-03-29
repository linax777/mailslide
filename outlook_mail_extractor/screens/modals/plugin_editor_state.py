"""State helpers for plugin editor modal."""

from typing import Any


def init_prompt_profiles_state(
    *,
    use_prompt_profile_editor: bool,
    current: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build initial prompt profile editor state."""
    if not use_prompt_profile_editor:
        return {}

    raw_profiles = current.get("prompt_profiles", {})
    parsed: dict[str, dict[str, Any]] = {}
    if isinstance(raw_profiles, dict):
        for key, value in raw_profiles.items():
            profile_key = str(key)
            if isinstance(value, dict):
                parsed[profile_key] = {
                    "version": value.get("version", 1),
                    "description": str(value.get("description", "")),
                    "system_prompt": str(value.get("system_prompt", "")),
                }
            else:
                parsed[profile_key] = {
                    "version": 1,
                    "description": "",
                    "system_prompt": str(value),
                }

    if parsed:
        return parsed

    fallback_prompt = str(current.get("system_prompt", "")).strip()
    return {
        "default_v1": {
            "version": 1,
            "description": "",
            "system_prompt": fallback_prompt,
        }
    }


def record_prompt_profile_rename(
    renames: dict[str, str],
    old_key: str,
    new_key: str,
) -> dict[str, str]:
    """Record and normalize a prompt profile key rename map."""
    if old_key == new_key:
        return dict(renames)

    rewrites: dict[str, str] = {}
    for source, target in renames.items():
        rewrites[source] = new_key if target == old_key else target
    rewrites[old_key] = new_key

    for source in list(rewrites.keys()):
        seen = {source}
        target = rewrites[source]
        while target in rewrites and target not in seen:
            seen.add(target)
            target = rewrites[target]
        rewrites[source] = target

    return {
        source: target
        for source, target in rewrites.items()
        if source and target and source != target
    }


def resolve_prompt_profile_rename(profile_key: str, renames: dict[str, str]) -> str:
    """Resolve chained prompt profile renames."""
    current = str(profile_key).strip()
    if not current:
        return ""

    seen = {current}
    while current in renames:
        current = renames[current]
        if current in seen:
            break
        seen.add(current)
    return current
