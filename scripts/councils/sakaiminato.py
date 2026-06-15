"""境港市議会 議員一覧ビルダー.

境港市公式サイトは robots.txt で User-agent: * に Disallow: / を
指定しているため、このファイルはスクレイピングを行わない。
data_sources/members_manual/sakaiminato-city.json の手動転記データから
docs/data/sakaiminato-city/members.json を生成する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "sakaiminato-city"
SOURCE_PATH = REPO_ROOT / "data_sources" / "members_manual" / f"{COUNCIL_ID}.json"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"

REQUIRED_MEMBER_KEYS = [
    "id",
    "council_id",
    "name",
    "name_kana",
    "faction",
    "elected_count",
    "positions",
    "committees",
    "photo_url",
    "source_url",
]


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_manual_source(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"{SOURCE_PATH}: root must be an object"]

    if data.get("council_id") != COUNCIL_ID:
        errors.append(f"{SOURCE_PATH}: council_id must be '{COUNCIL_ID}'")

    source_url = data.get("source_url")
    if source_url is not None and (
        not isinstance(source_url, str) or not source_url.startswith("https://")
    ):
        errors.append(f"{SOURCE_PATH}: source_url must be https:// URL or null")

    members = data.get("members")
    if not isinstance(members, list):
        errors.append(f"{SOURCE_PATH}: members must be a list")
        return errors
    if not members:
        errors.append(
            f"{SOURCE_PATH}: members is empty; KTの手動転記後に再実行してください"
        )
        return errors

    seen: set[str] = set()
    prefix = f"{COUNCIL_ID}--"
    for i, member in enumerate(members):
        label = f"{SOURCE_PATH}: members[{i}]"
        if not isinstance(member, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = [key for key in REQUIRED_MEMBER_KEYS if key not in member]
        for key in missing:
            errors.append(f"{label}: missing key '{key}'")

        member_id = member.get("id")
        if not isinstance(member_id, str) or not member_id.startswith(prefix):
            errors.append(f"{label}: id must start with '{prefix}'")
        elif member_id in seen:
            errors.append(f"{label}: duplicate id '{member_id}'")
        else:
            seen.add(member_id)

        if member.get("council_id") != COUNCIL_ID:
            errors.append(f"{label}: council_id must be '{COUNCIL_ID}'")
        if not member.get("name"):
            errors.append(f"{label}: name is required")
        if not isinstance(member.get("positions"), list):
            errors.append(f"{label}: positions must be a list")
        if not isinstance(member.get("committees"), list):
            errors.append(f"{label}: committees must be a list")

        member_source_url = member.get("source_url")
        if not isinstance(member_source_url, str) or not member_source_url.startswith(
            "https://"
        ):
            errors.append(f"{label}: source_url must start with 'https://'")

    return errors


class SakaiminatoManualBuilder(CouncilScraperBase):
    def build_members(self) -> list[dict]:
        print(f"reading {SOURCE_PATH} ...", flush=True)
        data = load_json(SOURCE_PATH)
        errors = validate_manual_source(data)
        if errors:
            print("Manual source validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            raise SystemExit(1)

        members = []
        for member in data["members"]:
            item = {key: member.get(key) for key in REQUIRED_MEMBER_KEYS}
            item.pop("source_url", None)
            item["photo_url"] = None
            members.append(item)
        return members


def main() -> int:
    builder = SakaiminatoManualBuilder()
    data = load_json(SOURCE_PATH)
    members = builder.build_members()
    print(f"parsed {len(members)} members")
    builder.assert_min_count(members, 12, "members")
    if not 12 <= len(members) <= 20:
        print(
            f"WARNING: expected 12-20 members, got {len(members)}",
            file=sys.stderr,
        )

    payload = {
        "council_id": COUNCIL_ID,
        "source_url": data["source_url"],
        "acquisition": "manual_transcription",
        "members": members,
    }
    force_photo_null(payload)
    apply_member_contract(
        payload,
        teisu=15,
        source_basis_date=data.get("source_basis_date") or "公式基準日記載なし",
        anchor_type="manual_official_roster_count",
        notes=[
            "KT確認済みの公式名簿手動転記15人を件数検算アンカーとして使用",
            "写真は取得せず、photo_urlは全員null",
        ],
    )
    builder.save_json(OUT_PATH, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
