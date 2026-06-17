"""Stable JSON output helpers for generated public data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

DEFAULT_VOLATILE_KEYS = frozenset({"updated_at", "retrieved_at", "last_verified"})


def strip_volatile_fields(
    value: Any,
    volatile_keys: Iterable[str] = DEFAULT_VOLATILE_KEYS,
) -> Any:
    """Return a copy of value with volatile timestamp fields removed."""
    key_set = set(volatile_keys)
    if isinstance(value, dict):
        return {
            key: strip_volatile_fields(item, key_set)
            for key, item in value.items()
            if key not in key_set
        }
    if isinstance(value, list):
        return [strip_volatile_fields(item, key_set) for item in value]
    return value


def has_entity_change(
    path: Path,
    new_payload: Any,
    volatile_keys: Iterable[str] = DEFAULT_VOLATILE_KEYS,
) -> bool:
    """Compare generated JSON with an existing file, ignoring volatile fields."""
    if not path.exists():
        return True

    try:
        existing_payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True

    return strip_volatile_fields(existing_payload, volatile_keys) != strip_volatile_fields(
        new_payload,
        volatile_keys,
    )


def write_json_if_entity_changed(
    path: Path,
    payload: Any,
    volatile_keys: Iterable[str] = DEFAULT_VOLATILE_KEYS,
) -> bool:
    """Write JSON only when non-volatile data changed. Return True if written."""
    if not has_entity_change(path, payload, volatile_keys):
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True
