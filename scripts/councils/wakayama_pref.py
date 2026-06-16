"""和歌山県議会 議員一覧スクレイパー.

ソース: https://www.pref.wakayama.lg.jp/prefg/200100/cms/d00213187.html
出力: docs/data/wakayama-pref/members.json
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
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "wakayama-pref"
SOURCE_URL = "https://www.pref.wakayama.lg.jp/prefg/200100/cms/d00213187.html"
GOJUON_URL = "https://www.pref.wakayama.lg.jp/prefg/200100/cms/d00213193.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 42
EXPECTED_MEMBERS = 41
EXPECTED_VACANCIES = 1
SOURCE_BASIS_DATE = "令和8年6月10日現在"

DISTRICT_RE = re.compile(r"^(?P<district>.+?)選挙区\s*[（(]\s*定数\s*(?P<capacity>[0-9０-９]+)\s*人\s*[)）]")
NAME_KANA_RE = re.compile(r"^(?P<name>.+?)\s*[（(]\s*(?P<kana>[^()（）]+?)\s*[)）]")


class WakayamaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        members, district_checks = self.parse_district_page(soup)
        ensure_unique_ids(members)

        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        vacancies = sum(int(item["vacancies"]) for item in district_checks)
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        if vacancies != EXPECTED_VACANCIES:
            raise RuntimeError(f"Vacancies {vacancies} != {EXPECTED_VACANCIES}")
        if len(members) + vacancies != capacity_total:
            raise RuntimeError("Wakayama member/vacancy/capacity check failed")

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "和歌山県議会 選挙区別名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "district_tables_with_contact_columns_ignored",
                "gojuon_source_url": GOJUON_URL,
                "capacity_total": capacity_total,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "vacancies": vacancies,
                "district_count": len(district_checks),
                "districts": district_checks,
                "notes": [
                    "選挙区別名簿の氏名・ふりがな・会派・選挙区・当選回数のみを取得",
                    "同表内の連絡先列は読まず、保存しない",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date=SOURCE_BASIS_DATE,
            vacancy_details=[
                {
                    "district": item["district"],
                    "ketsuin": item["vacancies"],
                    "source_url": SOURCE_URL,
                }
                for item in district_checks
                if int(item["vacancies"]) > 0
            ],
            anchor_source_url=SOURCE_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区別名簿の定数・欠員行を件数検算アンカーとして使用"],
        )
        return payload

    def parse_district_page(
        self, soup: BeautifulSoup
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        members: list[dict[str, object]] = []
        checks: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        for node in soup.find_all(["h2", "table"]):
            if node.name == "h2":
                label = normalize_text(node.get_text(" ", strip=True))
                match = DISTRICT_RE.match(label)
                if not match:
                    current = None
                    continue
                current = {
                    "district": normalize_text(match.group("district")),
                    "capacity": parse_count(match.group("capacity")) or 0,
                    "members": 0,
                    "vacancies": 0,
                    "source_url": SOURCE_URL,
                }
                checks.append(current)
                continue
            if node.name != "table" or current is None:
                continue
            for row in node.find_all("tr"):
                cells = row.find_all(["th", "td"], recursive=False)
                if len(cells) < 6:
                    continue
                link = cells[1].find("a", href=True)
                if not isinstance(link, Tag):
                    if "欠" in normalize_text(cells[1].get_text(" ", strip=True)):
                        current["vacancies"] = int(current["vacancies"]) + 1
                    continue
                name, kana = self.parse_name_kana(cells[1])
                member = build_member(
                    council_id=COUNCIL_ID,
                    name=name,
                    kana=kana,
                    district=str(current["district"]),
                    faction=cells[4].get_text(" ", strip=True),
                    elected_count=parse_count(cells[5].get_text(" ", strip=True)),
                    profile_url=urljoin(SOURCE_URL, str(link["href"])),
                )
                members.append(member)
                current["members"] = int(current["members"]) + 1
        for check in checks:
            check["vacancies"] = int(check["capacity"]) - int(check["members"])
            if int(check["vacancies"]) < 0:
                raise RuntimeError(
                    f"{check['district']}: members {check['members']} exceeds capacity {check['capacity']}"
                )
        return members, checks

    def parse_name_kana(self, cell: Tag) -> tuple[str, str | None]:
        text = normalize_text(cell.get_text(" ", strip=True))
        match = NAME_KANA_RE.match(text)
        if match:
            return match.group("name"), match.group("kana")
        link = cell.find("a")
        name = link.get_text(" ", strip=True) if isinstance(link, Tag) else text
        return name, None


def main() -> int:
    scraper = WakayamaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
