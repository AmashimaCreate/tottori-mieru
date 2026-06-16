"""青森県議会 議員一覧スクレイパー."""

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

COUNCIL_ID = "aomori-pref"
SOURCE_URL = "https://www.pref.aomori.lg.jp/soshiki/gikai/giin-gojuon_05.html"
DISTRICT_URL = "https://www.pref.aomori.lg.jp/soshiki/gikai/giin-senkyoku.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 48
EXPECTED_DISTRICTS = 16

NAME_KANA_RE = re.compile(r"(?P<name>.+?)[（(]\s*(?P<kana>[^()（）]+)\s*[)）]")


def clean_district(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"^[（(]?\s*[0-9０-９]+\s*[)）]?", "", text)
    return normalize_text(text)


class AomoriPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        roster_soup = self.fetch(SOURCE_URL)
        district_soup = self.fetch(DISTRICT_URL)
        members = self.parse_roster(roster_soup)
        district_checks, district_profiles = self.parse_districts(district_soup)

        roster_profiles = {str(member["official_profile_url"]) for member in members}
        if roster_profiles != district_profiles:
            raise RuntimeError(
                "Aomori roster/district profile mismatch: "
                f"roster_only={sorted(roster_profiles - district_profiles)}, "
                f"district_only={sorted(district_profiles - roster_profiles)}"
            )

        ensure_unique_ids(members)
        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"District count {len(district_checks)} != {EXPECTED_DISTRICTS}")

        vacancy_details = [
            {
                "district": item["district"],
                "ketsuin": item["vacancies"],
                "source_url": item["source_url"],
            }
            for item in district_checks
            if int(item["vacancies"]) > 0
        ]
        payload: dict[str, object] = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "青森県議会 議員の紹介（五十音順）",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_inline_table_with_district_anchor",
                "district_source_url": DISTRICT_URL,
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "parsed_members": len(members),
                "districts": district_checks,
                "notes": [
                    "五十音順ページから氏名・ふりがな・会派・選挙区・当選回数を抽出",
                    "選挙区別ページの定数とリンク集合で検算",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date="更新日付: 2026年5月25日",
            vacancy_details=vacancy_details,
            anchor_source_url=DISTRICT_URL,
            anchor_type="official_district_capacity",
            notes=["青森県議会選挙区別ページの定数を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup) -> list[dict[str, object]]:
        members: list[dict[str, object]] = []
        for table in soup.select("table.bc4"):
            headers = [normalize_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
            if not headers or not any("議員名" in header for header in headers):
                continue
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"], recursive=False)
                if len(cells) < 4:
                    continue
                link = cells[0].find("a", href=True)
                if not isinstance(link, Tag):
                    continue
                name_text = normalize_text(link.get_text(" ", strip=True))
                match = NAME_KANA_RE.search(name_text)
                name = match.group("name") if match else name_text
                kana = match.group("kana") if match else None
                members.append(
                    build_member(
                        council_id=COUNCIL_ID,
                        name=name,
                        kana=kana,
                        district=cells[2].get_text(" ", strip=True),
                        faction=cells[1].get_text(" ", strip=True),
                        elected_count=parse_count(cells[3].get_text(" ", strip=True)),
                        profile_url=urljoin(SOURCE_URL, str(link["href"])),
                    )
                )
        return members

    def parse_districts(self, soup: BeautifulSoup) -> tuple[list[dict[str, object]], set[str]]:
        table = soup.select_one("table.bc4")
        if not isinstance(table, Tag):
            raise RuntimeError("Aomori district table not found")
        checks: list[dict[str, object]] = []
        profiles: set[str] = set()
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < 4:
                continue
            capacity = parse_count(cells[2].get_text(" ", strip=True))
            if capacity is None:
                continue
            district = clean_district(cells[0].get_text(" ", strip=True))
            district_profiles = {
                urljoin(DISTRICT_URL, str(link["href"]))
                for link in cells[3].find_all("a", href=True)
            }
            profiles.update(district_profiles)
            current = len(district_profiles)
            vacancy = capacity - current
            if vacancy < 0:
                raise RuntimeError(f"{district}: members {current} exceeds capacity {capacity}")
            checks.append(
                {
                    "district": district,
                    "capacity": capacity,
                    "members": current,
                    "vacancies": vacancy,
                    "source_url": DISTRICT_URL,
                }
            )
        return checks, profiles


def main() -> int:
    scraper = AomoriPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
