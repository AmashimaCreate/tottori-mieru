"""Helpers for one-page prefectural assembly rosters.

The helpers are intentionally small and allowlist-oriented. They build only the
public roster fields used by the site and leave contact-rich profile bodies
alone.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.members_cms_table import make_slug, parse_int_like  # noqa: E402


HIRAGANA_TO_KATAKANA = str.maketrans(
    {chr(code): chr(code + 0x60) for code in range(ord("ぁ"), ord("ゖ") + 1)}
)

KANJI_NUMERALS = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\xa0", " ").replace("\u200b", "")
    value = value.replace("　", " ")
    return re.sub(r"\s+", " ", value).strip()


def compact_name(value: str | None) -> str:
    return normalize_text(value).replace(" ", "")


def kana_to_katakana(value: str | None) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    return text.translate(HIRAGANA_TO_KATAKANA)


KANA_ONLY_RE = re.compile(r"^[ぁ-ゖァ-ヺー・\s]+$")


def compact_kana_text(value: str | None) -> str | None:
    """Remove presentation-only spacing inside kana strings."""
    text = normalize_text(value)
    if not text:
        return None
    if KANA_ONLY_RE.fullmatch(text):
        return re.sub(r"\s+", "", text)
    return text


def parse_count(value: str | None) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    parsed = parse_int_like(text)
    if parsed is not None:
        return parsed
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = KANJI_NUMERALS.get(left, 1 if left == "" else 0)
        ones = KANJI_NUMERALS.get(right, 0) if right else 0
        return tens * 10 + ones
    return KANJI_NUMERALS.get(text)


def text_lines(tag: Tag) -> list[str]:
    return [
        normalize_text(line)
        for line in tag.get_text("\n", strip=True).splitlines()
        if normalize_text(line)
    ]


def build_member(
    *,
    council_id: str,
    name: str,
    kana: str | None,
    district: str | None,
    faction: str | None,
    elected_count: int | None,
    profile_url: str | None,
    committees: list[str] | None = None,
    positions: list[str] | None = None,
) -> dict[str, Any]:
    slug = make_slug(kana_to_katakana(kana) or "", name)
    if slug == "member":
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        slug = f"member-{digest}"
    return {
        "id": f"{council_id}--{slug}",
        "council_id": council_id,
        "name": compact_name(name),
        "name_kana": normalize_text(kana) or None,
        "district": normalize_text(district) or None,
        "faction": normalize_text(faction) or None,
        "elected_count": elected_count,
        "positions": positions or [],
        "committees": committees or [],
        "photo_url": None,
        "official_profile_url": profile_url,
    }


def ensure_unique_ids(members: list[dict[str, Any]]) -> None:
    seen: dict[str, int] = {}
    for member in members:
        member_id = str(member["id"])
        seen[member_id] = seen.get(member_id, 0) + 1
        if seen[member_id] == 1:
            continue
        member["id"] = f"{member_id}-{seen[member_id]}"


def expand_table(table: Tag) -> list[list[Tag]]:
    """Return a visual grid of table cells with row/col spans filled in."""
    grid: list[list[Tag]] = []
    spans: dict[tuple[int, int], Tag] = {}
    for row_index, row in enumerate(table.find_all("tr")):
        output_row: list[Tag] = []
        col_index = 0
        while (row_index, col_index) in spans:
            output_row.append(spans[(row_index, col_index)])
            col_index += 1

        for cell in row.find_all(["th", "td"], recursive=False):
            while (row_index, col_index) in spans:
                output_row.append(spans[(row_index, col_index)])
                col_index += 1
            rowspan = parse_count(str(cell.get("rowspan", "1"))) or 1
            colspan = parse_count(str(cell.get("colspan", "1"))) or 1
            for offset in range(colspan):
                output_row.append(cell)
                for row_offset in range(1, rowspan):
                    spans[(row_index + row_offset, col_index + offset)] = cell
            col_index += colspan
        grid.append(output_row)
    return grid
