"""兵庫県議会 議員一覧スクレイパー.

ソース: https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/50on/50on_ichiran23.html
出力: docs/data/hyogo-pref/members.json
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
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "hyogo-pref"
SOURCE_URL = "https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/50on/50on_ichiran23.html"
DISTRICT_URL = "https://web.pref.hyogo.lg.jp/gikai/giinshokai/shokai/senkyokubetsu/senkyo_ichiran.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 86
EXPECTED_MEMBERS = 82
EXPECTED_VACANCIES = 4
SOURCE_BASIS_DATE = "更新日 2026-01-16"

DISTRICT_RE = re.compile(r"^(?P<district>.+?)\s*[（(]\s*定数\s*(?P<capacity>[0-9０-９]+)\s*[)）]")
VACANCY_RE = re.compile(r"欠員\s*([0-9０-９]+)")


class HyogoPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        roster_soup = self.fetch(SOURCE_URL)
        district_soup = self.fetch(DISTRICT_URL)
        members = self.parse_roster(roster_soup)
        district_checks = self.parse_district_checks(district_soup)

        ensure_unique_ids(members)
        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        vacancies = sum(int(item["vacancies"]) for item in district_checks)
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if vacancies != EXPECTED_VACANCIES:
            raise RuntimeError(f"Vacancies {vacancies} != {EXPECTED_VACANCIES}")
        if len(members) + vacancies != capacity_total:
            raise RuntimeError("Hyogo member/vacancy/capacity check failed")

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "兵庫県議会 五十音別一覧表",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_roster_table_with_district_capacity",
                "district_source_url": DISTRICT_URL,
                "capacity_total": capacity_total,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "vacancies": vacancies,
                "district_count": len(district_checks),
                "districts": district_checks,
                "notes": [
                    "五十音別一覧表の氏名・ふりがな・選挙区・当選回数・会派のみを取得",
                    "選挙区別一覧表の定数・欠員表記を件数検算アンカーとして使用",
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
                    "source_url": DISTRICT_URL,
                }
                for item in district_checks
                if int(item["vacancies"]) > 0
            ],
            anchor_source_url=DISTRICT_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区別一覧表の定数・欠員表記を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup) -> list[dict[str, object]]:
        table = soup.find("table", class_="datatable")
        if not isinstance(table, Tag):
            raise RuntimeError("Hyogo roster table not found")
        members: list[dict[str, object]] = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 5:
                continue
            link = cells[0].find("a", href=True)
            if not isinstance(link, Tag):
                continue
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=link.get_text(" ", strip=True),
                    kana=cells[1].get_text(" ", strip=True),
                    district=cells[2].get_text(" ", strip=True),
                    elected_count=parse_count(cells[3].get_text(" ", strip=True)),
                    faction=cells[4].get_text(" ", strip=True),
                    profile_url=urljoin(SOURCE_URL, str(link["href"])),
                )
            )
        return members

    def parse_district_checks(self, soup: BeautifulSoup) -> list[dict[str, object]]:
        checks: list[dict[str, object]] = []
        seen: set[str] = set()
        for table in soup.find_all("table", class_="datatable"):
            for grid_row in expand_table(table):
                if not grid_row:
                    continue
                label = normalize_text(grid_row[0].get_text(" ", strip=True))
                match = DISTRICT_RE.search(label)
                if not match or label in seen:
                    continue
                seen.add(label)
                vacancy_match = VACANCY_RE.search(label)
                checks.append(
                    {
                        "district": normalize_text(match.group("district")),
                        "capacity": parse_count(match.group("capacity")) or 0,
                        "vacancies": parse_count(vacancy_match.group(1)) if vacancy_match else 0,
                        "source_url": DISTRICT_URL,
                    }
                )
        if not checks:
            raise RuntimeError("Hyogo district checks not found")
        return checks


def main() -> int:
    scraper = HyogoPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
