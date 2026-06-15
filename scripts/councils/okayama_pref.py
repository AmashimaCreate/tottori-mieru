"""岡山県議会 議員一覧スクレイパー.

ソース: https://www.pref.okayama.jp/site/gikai/03-04.html
出力: docs/data/okayama-pref/members.json
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    compact_name,
    ensure_unique_ids,
    expand_table,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract  # noqa: E402

COUNCIL_ID = "okayama-pref"
SOURCE_URL = "https://www.pref.okayama.jp/site/gikai/03-04.html"
TERM_URL = "https://www.pref.okayama.jp/site/gikai/03-02.html"
CAPACITY_URL = "https://www.pref.okayama.jp/site/gikai/556455.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 55
EXPECTED_MEMBERS = 54
EXPECTED_DISTRICTS = 19

FACTION_MAP = {
    "自民": "自由民主党岡山県議団",
    "民県": "民主・県民クラブ",
    "公明": "公明党岡山県議団",
    "共産": "日本共産党岡山県議会議員団",
}


def profile_key(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.path}#{parsed.fragment}" if parsed.fragment else parsed.path


class OkayamaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        main_soup = self.fetch(SOURCE_URL)
        term_soup = self.fetch(TERM_URL)
        capacity_soup = self.fetch(CAPACITY_URL)

        capacities = self.parse_capacity_table(capacity_soup)
        term_counts = self.parse_term_table(term_soup)
        rows = self.parse_seat_table(main_soup)

        members: list[dict[str, object]] = []
        district_member_counts: Counter[str] = Counter()
        seats: list[int] = []
        missing_term_keys: list[str] = []
        for row in rows:
            district_member_counts[row["district"]] += 1
            seats.append(int(row["seat"]))
            term_key = f"{compact_name(str(row['name']))}|{row['district']}"
            elected_count = term_counts.get(term_key)
            if elected_count is None:
                missing_term_keys.append(term_key)
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=str(row["name"]),
                    kana=None,
                    district=str(row["district"]),
                    faction=FACTION_MAP.get(str(row["faction"]), str(row["faction"])),
                    elected_count=elected_count,
                    profile_url=str(row["profile_url"]),
                )
            )

        if missing_term_keys:
            raise RuntimeError(f"Okayama elected_count join failed: {missing_term_keys}")
        ensure_unique_ids(members)

        district_checks: list[dict[str, object]] = []
        vacancies = 0
        for district, capacity in capacities.items():
            current = district_member_counts[district]
            vacancy = capacity - current
            if vacancy < 0:
                raise RuntimeError(f"{district}: members {current} exceeds capacity {capacity}")
            vacancies += vacancy
            district_checks.append(
                {
                    "district": district,
                    "capacity": capacity,
                    "members": current,
                    "vacancies": vacancy,
                    "source_url": CAPACITY_URL,
                }
            )

        capacity_total = sum(capacities.values())
        missing_seats = sorted(set(range(1, capacity_total + 1)) - set(seats))
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if len(capacities) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"Expected {EXPECTED_DISTRICTS} districts, parsed {len(capacities)}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        if len(term_counts) != len(members):
            raise RuntimeError(f"Term table has {len(term_counts)} members; roster has {len(members)}")
        if vacancies != capacity_total - len(members):
            raise RuntimeError("Okayama vacancy total mismatch")

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "岡山県議会 議席順名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_seat_table_with_term_join",
                "term_url": TERM_URL,
                "capacity_url": CAPACITY_URL,
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "vacancies": vacancies,
                "missing_seats": missing_seats,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "term_rows": len(term_counts),
                "districts": district_checks,
                "notes": [
                    "議席順名簿から氏名・会派・選挙区、期別名簿から当選回数を結合",
                    "岡山市北区・加賀郡は定数8・現員7。議席48が欠番",
                    "会派略称は公式凡例に基づき展開",
                    "会派別名簿はWAF拒否の可能性があるため依存しない",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        vacancy_details = [
            {
                "district": district["district"],
                "ketsuin": district["vacancies"],
                "source_url": district["source_url"],
            }
            for district in district_checks
            if int(district["vacancies"]) > 0
        ]
        for seat in missing_seats:
            vacancy_details.append({"seat_number": seat, "source_url": SOURCE_URL})
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date="議席順名簿 掲載日: 2025年5月15日更新",
            vacancy_details=vacancy_details,
            anchor_source_url=CAPACITY_URL,
            anchor_type="official_district_capacity",
            notes=["議会定数と選挙区ページの定数表を件数検算アンカーとして使用"],
        )
        return payload

    def parse_seat_table(self, soup: BeautifulSoup) -> list[dict[str, object]]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Okayama seat table not found")
        rows: list[dict[str, object]] = []
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["th", "td"], recursive=False)
            if len(cells) < 4:
                continue
            seat = parse_count(cells[0].get_text(" ", strip=True))
            link = cells[2].find("a", href=True)
            if seat is None or not isinstance(link, Tag):
                continue
            rows.append(
                {
                    "seat": seat,
                    "faction": normalize_text(cells[1].get_text(" ", strip=True)),
                    "name": normalize_text(link.get_text(" ", strip=True)),
                    "district": normalize_text(cells[3].get_text(" ", strip=True)),
                    "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                }
            )
        return rows

    def parse_term_table(self, soup: BeautifulSoup) -> dict[str, int]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Okayama term table not found")
        terms: dict[str, int] = {}
        for row in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in row]
            for start in (0, 5):
                if len(values) < start + 4:
                    continue
                elected_count = parse_count(values[start])
                name = values[start + 1]
                district = values[start + 3]
                if elected_count is None or not name or not district:
                    continue
                terms[f"{compact_name(name)}|{district}"] = elected_count
        return terms

    def parse_capacity_table(self, soup: BeautifulSoup) -> dict[str, int]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Okayama capacity table not found")
        capacities: dict[str, int] = {}
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"], recursive=False)
            for index in range(0, len(cells) - 1, 2):
                district = normalize_text(cells[index].get_text(" ", strip=True))
                capacity = parse_count(cells[index + 1].get_text(" ", strip=True))
                if district and capacity is not None:
                    capacities[district] = capacity
        return capacities


def main() -> int:
    scraper = OkayamaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
