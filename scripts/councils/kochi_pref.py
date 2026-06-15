"""高知県議会 議員一覧スクレイパー.

ソース: https://gikai.pref.kochi.lg.jp/member/categories/
出力: docs/data/kochi-pref/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    ensure_unique_ids,
    normalize_text,
    parse_count,
    text_lines,
)
from scripts.base import CouncilScraperBase  # noqa: E402

COUNCIL_ID = "kochi-pref"
SOURCE_URL = "https://gikai.pref.kochi.lg.jp/member/categories/"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 37
EXPECTED_VACANCIES = 1
EXPECTED_MEMBERS = 36
EXPECTED_MISSING_SEATS = [23]

FACTION_RE = re.compile(r"^(.+?)[（(]\s*([0-9０-９]+)\s*人\s*[)）]$")


def parse_name_cell(cell: Tag) -> tuple[str, str | None]:
    lines = text_lines(cell)
    if not lines:
        raise RuntimeError("Kochi name cell is empty")
    name = lines[0]
    kana = None
    if len(lines) > 1:
        match = re.search(r"[（(](.+?)[)）]", lines[1])
        kana = normalize_text(match.group(1)) if match else normalize_text(lines[1])
    return name, kana


class KochiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        members: list[dict[str, object]] = []
        faction_checks: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        seats: list[int] = []

        for row in soup.find_all("tr"):
            heading = row.find("th", class_="gm-seito")
            if isinstance(heading, Tag):
                label = normalize_text(heading.get_text(" ", strip=True))
                match = FACTION_RE.match(label)
                if not match:
                    raise RuntimeError(f"Kochi faction heading not parseable: {label}")
                current = {
                    "faction": normalize_text(match.group(1)),
                    "declared_members": parse_count(match.group(2)) or 0,
                    "members": 0,
                }
                faction_checks.append(current)
                continue

            cells = row.find_all(["td", "th"], recursive=False)
            if current is None or len(cells) < 5:
                continue
            seat = parse_count(cells[0].get_text(" ", strip=True))
            if seat is None:
                continue
            name, kana = parse_name_cell(cells[2])
            committee = normalize_text(cells[-2].get_text(" ", strip=True))
            district = normalize_text(cells[-1].get_text(" ", strip=True))
            positions = []
            if "委員長" in committee or "副委員長" in committee:
                positions.append(committee)
            member = build_member(
                council_id=COUNCIL_ID,
                name=name,
                kana=kana,
                district=district,
                faction=str(current["faction"]),
                elected_count=None,
                profile_url=SOURCE_URL,
                committees=[committee] if committee else [],
                positions=positions,
            )
            members.append(member)
            seats.append(seat)
            current["members"] = int(current["members"]) + 1

        ensure_unique_ids(members)
        for faction in faction_checks:
            if int(faction["declared_members"]) != int(faction["members"]):
                raise RuntimeError(
                    f"{faction['faction']}: declared {faction['declared_members']} "
                    f"!= parsed {faction['members']}"
                )
        missing_seats = sorted(set(range(1, EXPECTED_CAPACITY + 1)) - set(seats))
        if missing_seats != EXPECTED_MISSING_SEATS:
            raise RuntimeError(f"Kochi missing seats {missing_seats} != {EXPECTED_MISSING_SEATS}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        if len(members) + len(missing_seats) != EXPECTED_CAPACITY:
            raise RuntimeError("Kochi capacity check failed")

        return {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "高知県議会 議員名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_faction_table",
                "capacity_total": EXPECTED_CAPACITY,
                "vacancies": len(missing_seats),
                "missing_seats": missing_seats,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "factions": faction_checks,
                "notes": [
                    "会派見出しの人数と会派内の取得人数を照合",
                    "議席番号23が欠番のため欠員1として記録",
                    "五十音順ページに当選回数は見当たらないためelected_countはnull",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }


def main() -> int:
    scraper = KochiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
