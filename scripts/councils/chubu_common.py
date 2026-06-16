"""Shared helpers for Chubu prefectural assembly rosters."""

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


KANA_RE = re.compile(r"^[ぁ-ゖァ-ヺー・\s]+$")


def out_path(council_id: str) -> Path:
    return REPO_ROOT / "docs" / "data" / council_id / "members.json"


def is_kana_token(token: str) -> bool:
    return bool(token) and KANA_RE.fullmatch(token) is not None


def clean_role_prefix(text: str) -> tuple[str, list[str]]:
    value = normalize_text(text)
    positions: list[str] = []
    for role in ("副議長", "議長"):
        if value.startswith(role):
            positions.append(role)
            value = normalize_text(value[len(role) :])
    return value, positions


def parse_name_kana(value: str) -> tuple[str, str | None, list[str]]:
    text, positions = clean_role_prefix(value)
    paren = re.search(r"(.+?)[（(]\s*([^（）()]+?)\s*[）)]", text)
    if paren:
        return normalize_text(paren.group(1)), normalize_text(paren.group(2)), positions

    tokens = normalize_text(text).split()
    if not tokens:
        return "", None, positions

    if is_kana_token(tokens[0]):
        split_at = 0
        while split_at < len(tokens) and is_kana_token(tokens[split_at]):
            split_at += 1
        kana = " ".join(tokens[:split_at])
        name = " ".join(tokens[split_at:])
        return normalize_text(name), normalize_text(kana) or None, positions

    for index, token in enumerate(tokens):
        if is_kana_token(token):
            name = " ".join(tokens[:index])
            kana = " ".join(tokens[index:])
            return normalize_text(name), normalize_text(kana) or None, positions
    return normalize_text(text), None, positions


def parse_faction_and_count(value: str) -> tuple[str | None, int | None]:
    text = normalize_text(value)
    match = re.search(r"(.+?)\s*当選\s*([0-9０-９一二三四五六七八九十]+)\s*回", text)
    if not match:
        return text or None, parse_count(text)
    return normalize_text(match.group(1)) or None, parse_count(match.group(2))


def link_url(cell: Tag, base_url: str) -> str | None:
    link = cell.find("a", href=True)
    if not link:
        return None
    return urljoin(base_url, str(link["href"]))


def capacity_from_label(label: str) -> tuple[str, int | None, int]:
    text = normalize_text(label)
    district = re.split(r"[（(]", text, maxsplit=1)[0].strip()
    capacity_match = re.search(r"(?:定数|定員)\s*([0-9０-９一二三四五六七八九十]+)", text)
    if not capacity_match:
        capacity_match = re.search(r"[（(]\s*([0-9０-９一二三四五六七八九十]+)\s*人\s*[）)]", text)
    vacancy_match = re.search(r"欠員\s*([0-9０-９一二三四五六七八九十]+)", text)
    capacity = parse_count(capacity_match.group(1)) if capacity_match else None
    vacancy = parse_count(vacancy_match.group(1)) if vacancy_match else 0
    return district, capacity, vacancy or 0


def build_payload(
    *,
    council_id: str,
    source_url: str,
    source_name: str,
    members: list[dict[str, Any]],
    teisu: int,
    source_basis_date: str,
    vacancy_details: list[dict[str, Any]] | None = None,
    anchor_source_url: str | None = None,
    anchor_type: str = "official_roster_count",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    ensure_unique_ids(members)
    payload: dict[str, Any] = {
        "council_id": council_id,
        "source_url": source_url,
        "source_name": source_name,
        "acquisition": "scraping",
        "members": members,
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


def make_member(
    *,
    council_id: str,
    name_text: str,
    district: str | None,
    faction: str | None,
    elected_count: int | None,
    profile_url: str | None,
    committees: list[str] | None = None,
    positions: list[str] | None = None,
) -> dict[str, Any]:
    name, kana, parsed_positions = parse_name_kana(name_text)
    return build_member(
        council_id=council_id,
        name=compact_name(name),
        kana=kana,
        district=district,
        faction=faction,
        elected_count=elected_count,
        profile_url=profile_url,
        committees=committees,
        positions=[*(positions or []), *parsed_positions],
    )
