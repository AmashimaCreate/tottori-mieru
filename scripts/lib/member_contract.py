"""Shared contract metadata for generated member rosters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def verified_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def apply_member_contract(
    payload: dict[str, Any],
    *,
    teisu: int,
    source_basis_date: str | None = None,
    vacancy_details: list[dict[str, Any]] | None = None,
    anchor_source_url: str | None = None,
    anchor_type: str = "official_roster_count",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Attach count-check metadata and fail on impossible roster counts.

    `teisu` is the count anchor used for automatic update safety. When the
    official source exposes only the current roster and no separate capacity
    table, callers should pass the official roster count and state that in
    `anchor_type`/`notes`.
    """

    members = payload.get("members")
    if not isinstance(members, list):
        raise RuntimeError("member payload must contain a members list")

    genin = len(members)
    ketsuin = teisu - genin
    if genin > teisu:
        raise RuntimeError(f"member count {genin} exceeds teisu {teisu}")
    if ketsuin > 0 and not vacancy_details:
        raise RuntimeError(
            f"member count {genin} is below teisu {teisu}, but vacancy details are missing"
        )

    payload["source_basis_date"] = source_basis_date or "公式基準日記載なし"
    payload["last_verified"] = verified_date()
    payload["teisu"] = teisu
    payload["genin"] = genin
    payload["ketsuin"] = ketsuin

    checks = dict(payload.get("checks") or {})
    checks.update(
        {
            "anchor_type": anchor_type,
            "anchor_source_url": anchor_source_url or payload.get("source_url"),
            "source_basis_date": payload["source_basis_date"],
            "last_verified": payload["last_verified"],
            "teisu": teisu,
            "genin": genin,
            "ketsuin": ketsuin,
            "parsed_members": genin,
            "vacancy_details": vacancy_details or [],
        }
    )
    if notes:
        existing = [str(item) for item in checks.get("notes", [])]
        for note in notes:
            if note not in existing:
                existing.append(note)
        checks["notes"] = existing
    payload["checks"] = checks
    return payload


def force_photo_null(payload: dict[str, Any]) -> dict[str, Any]:
    for member in payload.get("members", []):
        if isinstance(member, dict):
            member["photo_url"] = None
    return payload
