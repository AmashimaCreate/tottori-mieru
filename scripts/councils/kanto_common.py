"Shared helpers for Kanto prefectural assembly rosters."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    compact_name,
    ensure_unique_ids,
    normalize_text,
    parse_count,
)
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402


def out_path(council_id: str) -> Path:
    return REPO_ROOT / "docs" / "data" / council_id / "members.json"


def absolute_url(base_url: str, href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(base_url, href)


def clean(value: str | None) -> str:
    return normalize_text(value).replace("\u3000", " ")


def empty_to_none(value: str | None) -> str | None:
    text = clean(value)
    if not text or text in {"-", "ー", "ｰ", "　", " "}:
        return None
    return text


def parse_district_capacity(label: str) -> tuple[str, int | None, int]:
    text = clean(label)
    district = re.split(r"[（(]", text, maxsplit=1)[0]
    district = re.sub(r"選挙区$", "", district).strip()
    capacity_match = re.search(r"(?:定数|定員)\s*([0-9０-９一二三四五六七八九十]+)\s*人?", text)
    if not capacity_match:
        capacity_match = re.search(r"[（(]\s*([0-9０-９一二三四五六七八九十]+)\s*[）)]", text)
    vacancy_match = re.search(r"欠員\s*([0-9０-９一二三四五六七八九十]+)", text)
    return district, parse_count(capacity_match.group(1)) if capacity_match else None, (
        parse_count(vacancy_match.group(1)) if vacancy_match else 0
    ) or 0


def split_name_kana(value: str) -> tuple[str, str | None]:
    text = clean(value)
    match = re.match(r"(.+?)[（(]([^（）()]+)[）)]$", text)
    if match:
        return clean(match.group(1)), clean(match.group(2))
    return text, None


def text_list(cell: Tag | None) -> list[str]:
    if cell is None:
        return []
    return [
        clean(line)
        for line in cell.get_text("\n", strip=True).splitlines()
        if clean(line)
    ]


def add_unique(items: list[str], value: str | None) -> None:
    text = empty_to_none(value)
    if text and text not in items:
        items.append(text)


def committee_list(*values: str | None) -> list[str]:
    committees: list[str] = []
    for value in values:
        text = empty_to_none(value)
        if not text:
            continue
        parts = re.split(r"[\n/／、,]+", text)
        for part in parts:
            add_unique(committees, part)
    return committees


def member(
    *,
    council_id: str,
    name: str,
    kana: str | None = None,
    district: str | None,
    faction: str | None,
    elected_count: int | None,
    profile_url: str | None,
    committees: list[str] | None = None,
    positions: list[str] | None = None,
) -> dict[str, Any]:
    return build_member(
        council_id=council_id,
        name=compact_name(name),
        kana=empty_to_none(kana),
        district=empty_to_none(district),
        faction=empty_to_none(faction),
        elected_count=elected_count,
        profile_url=profile_url,
        committees=committees or [],
        positions=positions or [],
    )


def build_payload(
    *,
    council_id: str,
    source_url: str,
    source_name: str,
    members: list[dict[str, Any]],
    teisu: int,
    source_basis_date: str,
    vacancy_details: list[dict[str, Any]] | None,
    anchor_source_url: str | None = None,
    anchor_type: str = "official_district_capacity",
    notes: list[str] | None = None,
    checks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_unique_ids(members)
    payload: dict[str, Any] = {
        "council_id": council_id,
        "source_url": source_url,
        "source_name": source_name,
        "acquisition": "scraping",
        "members": members,
        "checks": checks or {},
    }
    force_photo_null(payload)
    apply_member_contract(
        payload,
        teisu=teisu,
        source_basis_date=source_basis_date,
        vacancy_details=vacancy_details or [],
        anchor_source_url=anchor_source_url or source_url,
        anchor_type=anchor_type,
        notes=notes or [],
    )
    return payload
