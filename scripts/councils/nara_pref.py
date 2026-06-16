"""奈良県議会 議員一覧スクレイパー.

ソース: https://www.pref.nara.lg.jp/n161/52534.html
出力: docs/data/nara-pref/members.json
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

COUNCIL_ID = "nara-pref"
SOURCE_URL = "https://www.pref.nara.lg.jp/n161/52534.html"
DISTRICT_URL = "https://www.pref.nara.lg.jp/n161/18534.html"
CORRECT_NAME_URL = "https://www.pref.nara.lg.jp/n161/p114004.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 43
EXPECTED_MEMBERS = 40
EXPECTED_VACANCIES = 3
SOURCE_BASIS_DATE = "更新日 2026-04-24"


class NaraPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        roster_soup = self.fetch(SOURCE_URL)
        district_soup = self.fetch(DISTRICT_URL)
        members = self.parse_roster(roster_soup)
        district_check = self.parse_capacity(district_soup)

        ensure_unique_ids(members)
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        if district_check["capacity"] != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity {district_check['capacity']} != {EXPECTED_CAPACITY}")
        if district_check["members"] != EXPECTED_MEMBERS:
            raise RuntimeError(f"Current members {district_check['members']} != {EXPECTED_MEMBERS}")
        if district_check["vacancies"] != EXPECTED_VACANCIES:
            raise RuntimeError(f"Vacancies {district_check['vacancies']} != {EXPECTED_VACANCIES}")

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "奈良県議会 議員名簿（五十音順）",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_roster_table",
                "district_source_url": DISTRICT_URL,
                "correct_name_source_url": CORRECT_NAME_URL,
                "capacity_total": district_check["capacity"],
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "vacancies": district_check["vacancies"],
                "notes": [
                    "五十音順名簿の氏名・ふりがな・選挙区・当選回数・会派のみを取得",
                    "選挙区別名簿の定数43名・現員40名表記を件数検算アンカーとして使用",
                    "正確な表記ページは確認したが、機械取得できる正字セルが空のため五十音順名簿の表記を保持",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=district_check["capacity"],
            source_basis_date=SOURCE_BASIS_DATE,
            vacancy_details=[
                {
                    "label": "選挙区別名簿 定数43名（現員40名）",
                    "ketsuin": district_check["vacancies"],
                    "source_url": DISTRICT_URL,
                }
            ],
            anchor_source_url=DISTRICT_URL,
            anchor_type="official_district_capacity_summary",
            notes=["選挙区別名簿の定数・現員表記を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup) -> list[dict[str, object]]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Nara roster table not found")
        members: list[dict[str, object]] = []
        for cells in expand_table(table):
            if len(cells) < 6:
                continue
            link = cells[1].find("a", href=True)
            if not isinstance(link, Tag):
                continue
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=link.get_text(" ", strip=True),
                    kana=cells[2].get_text(" ", strip=True),
                    district=cells[3].get_text(" ", strip=True),
                    elected_count=parse_count(cells[4].get_text(" ", strip=True)),
                    faction=cells[5].get_text(" ", strip=True),
                    profile_url=urljoin(SOURCE_URL, str(link["href"])),
                )
            )
        return members

    def parse_capacity(self, soup: BeautifulSoup) -> dict[str, int]:
        text = normalize_text(soup.get_text(" ", strip=True))
        match = re.search(
            r"定数\s*([0-9０-９]+)\s*名\s*[（(]\s*現員\s*([0-9０-９]+)\s*名\s*[)）]",
            text,
        )
        if not match:
            raise RuntimeError("Nara capacity summary not found")
        capacity = parse_count(match.group(1)) or 0
        members = parse_count(match.group(2)) or 0
        return {"capacity": capacity, "members": members, "vacancies": capacity - members}


def main() -> int:
    scraper = NaraPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
