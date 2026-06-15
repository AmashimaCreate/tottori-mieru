"""愛媛県議会 議員一覧スクレイパー.

ソース: https://www.pref.ehime.jp/site/gikai/12716.html
出力: docs/data/ehime-pref/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    ensure_unique_ids,
    expand_table,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402

COUNCIL_ID = "ehime-pref"
SOURCE_URL = "https://www.pref.ehime.jp/site/gikai/12716.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_DISTRICTS = 13
EXPECTED_CAPACITY = 47
EXPECTED_VACANCIES = 1
EXPECTED_MEMBERS = 46


class EhimePrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        table = self.find_member_table(soup)
        members: list[dict[str, object]] = []
        districts: dict[str, dict[str, object]] = {}

        for row in expand_table(table)[1:]:
            if len(row) < 5:
                continue
            district = normalize_text(row[0].get_text(" ", strip=True))
            capacity = parse_count(row[1].get_text(" ", strip=True))
            name_cell = row[2]
            link = name_cell.find("a", href=True)
            if not isinstance(link, Tag):
                continue
            name = normalize_text(link.get_text(" ", strip=True))
            if not name:
                continue
            faction = normalize_text(row[3].get_text(" ", strip=True)) or None
            elected_count = parse_count(row[4].get_text(" ", strip=True))
            if district not in districts:
                districts[district] = {
                    "district": district,
                    "capacity": capacity or 0,
                    "members": 0,
                    "vacancies": 0,
                    "source_url": SOURCE_URL,
                }
            districts[district]["members"] = int(districts[district]["members"]) + 1
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=name,
                    kana=None,
                    district=district,
                    faction=faction,
                    elected_count=elected_count,
                    profile_url=urljoin(SOURCE_URL, str(link["href"])),
                )
            )

        for district in districts.values():
            district["vacancies"] = int(district["capacity"]) - int(district["members"])
            if int(district["vacancies"]) < 0:
                raise RuntimeError(
                    f"{district['district']}: members {district['members']} exceeds capacity {district['capacity']}"
                )

        ensure_unique_ids(members)
        district_checks = list(districts.values())
        capacity_total = sum(int(d["capacity"]) for d in district_checks)
        vacancies = sum(int(d["vacancies"]) for d in district_checks)
        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"Expected {EXPECTED_DISTRICTS} districts, parsed {len(district_checks)}")
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if vacancies != EXPECTED_VACANCIES:
            raise RuntimeError(f"Vacancies {vacancies} != {EXPECTED_VACANCIES}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")

        return {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "愛媛県議会 議員名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_rowspan_table",
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "vacancies": vacancies,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "districts": district_checks,
                "notes": [
                    "rowspan/colspanを展開して選挙区・定数をキャリーダウン",
                    "西条市は公式表で定数4・現員3のため欠員1として記録",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }

    def find_member_table(self, soup: BeautifulSoup) -> Tag:
        for table in soup.find_all("table"):
            headers = {normalize_text(th.get_text(" ", strip=True)) for th in table.find_all("th")}
            if {"選挙区", "定数", "氏名", "所属会派等", "当選回数"}.issubset(headers):
                return table
        raise RuntimeError("Ehime member table not found")


def main() -> int:
    scraper = EhimePrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
