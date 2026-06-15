"""山口県議会 議員一覧スクレイパー.

ソース: https://www.pref.yamaguchi.lg.jp/site/gikai/25262.html
出力: docs/data/yamaguchi-pref/members.json
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
    ensure_unique_ids,
    expand_table,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract  # noqa: E402

COUNCIL_ID = "yamaguchi-pref"
SOURCE_URL = "https://www.pref.yamaguchi.lg.jp/site/gikai/25262.html"
FACTION_URL = "https://www.pref.yamaguchi.lg.jp/site/gikai/25264.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_DISTRICTS = 15
EXPECTED_CAPACITY = 47
EXPECTED_MEMBERS = 47


def profile_key(url: str) -> str:
    return urlparse(url).path


class YamaguchiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        main_soup = self.fetch(SOURCE_URL)
        faction_soup = self.fetch(FACTION_URL)
        faction_by_profile, faction_counts = self.parse_faction_table(faction_soup)
        rows, district_checks = self.parse_member_table(main_soup)

        members: list[dict[str, object]] = []
        missing_factions: list[str] = []
        profile_fields_by_url: dict[str, dict[str, object]] = {}
        for row in rows:
            key = profile_key(str(row["profile_url"]))
            faction = faction_by_profile.get(key)
            if not faction:
                missing_factions.append(key)
            profile_fields = profile_fields_by_url.get(str(row["profile_url"]))
            if profile_fields is None:
                profile_fields = self.parse_profile(self.fetch(str(row["profile_url"])))
                profile_fields_by_url[str(row["profile_url"])] = profile_fields
            committees = profile_fields.get("committees")
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=str(row["name"]),
                    kana=profile_fields.get("kana") if isinstance(profile_fields.get("kana"), str) else None,
                    district=str(row["district"]),
                    faction=faction,
                    elected_count=profile_fields.get("elected_count") if isinstance(profile_fields.get("elected_count"), int) else None,
                    profile_url=str(row["profile_url"]),
                    committees=committees if isinstance(committees, list) else [],
                )
            )

        if missing_factions:
            raise RuntimeError(f"Yamaguchi faction join failed: {missing_factions}")
        ensure_unique_ids(members)
        capacity_total = sum(int(d["capacity"]) for d in district_checks)
        vacancies = sum(int(d["vacancies"]) for d in district_checks)
        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"Expected {EXPECTED_DISTRICTS} districts, parsed {len(district_checks)}")
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        if vacancies != EXPECTED_CAPACITY - EXPECTED_MEMBERS:
            raise RuntimeError(f"Vacancies {vacancies} != {EXPECTED_CAPACITY - EXPECTED_MEMBERS}")
        if sum(faction_counts.values()) != len(members):
            raise RuntimeError(
                f"Faction count total {sum(faction_counts.values())} != member count {len(members)}"
            )

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "山口県議会 議員名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_rowspan_table_with_faction_join",
                "faction_url": FACTION_URL,
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "vacancies": vacancies,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "faction_counts": faction_counts,
                "districts": district_checks,
                "notes": [
                    "議員名簿の選挙区・定数をrowspan展開し、会派別名簿をプロフィールURLキーで結合",
                    "公式ページ実物では柳井市は定数1・現員1のため欠員なし",
                    "個別プロフィールはふりがな・当選回数・所属委員会のみ許可リストで取得",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date="議員名簿 更新日: 2026年4月21日 / 会派別 令和8年3月10日現在",
            anchor_source_url=SOURCE_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区別定数列を件数検算アンカーとして使用"],
        )
        return payload

    def parse_member_table(
        self,
        soup: BeautifulSoup,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Yamaguchi member table not found")
        rows: list[dict[str, object]] = []
        districts: dict[str, dict[str, object]] = {}
        for grid_row in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in grid_row]
            if len(values) < 2:
                continue
            match = re.match(r"(.+?)\s*[（(]\s*([0-9０-９]+)", values[0])
            if not match:
                continue
            district = normalize_text(match.group(1))
            capacity = parse_count(match.group(2)) or 0
            link = grid_row[1].find("a", href=True)
            if not isinstance(link, Tag):
                continue
            name = normalize_text(link.get_text(" ", strip=True))
            if not name:
                continue
            if district not in districts:
                districts[district] = {
                    "district": district,
                    "capacity": capacity,
                    "members": 0,
                    "vacancies": 0,
                    "source_url": SOURCE_URL,
                }
            districts[district]["members"] = int(districts[district]["members"]) + 1
            rows.append(
                {
                    "district": district,
                    "name": name,
                    "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                }
            )

        district_checks = list(districts.values())
        for district in district_checks:
            district["vacancies"] = int(district["capacity"]) - int(district["members"])
            if int(district["vacancies"]) < 0:
                raise RuntimeError(
                    f"{district['district']}: members {district['members']} exceeds capacity {district['capacity']}"
                )
        return rows, district_checks

    def parse_faction_table(self, soup: BeautifulSoup) -> tuple[dict[str, str], dict[str, int]]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Yamaguchi faction table not found")
        current_faction: str | None = None
        faction_by_profile: dict[str, str] = {}
        declared_counts: dict[str, int] = {}
        actual_counts: Counter[str] = Counter()
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            first = normalize_text(cells[0].get_text(" ", strip=True))
            match = re.match(r"(.+?)\s*[（(]\s*([0-9０-９]+)\s*人", first)
            if match:
                current_faction = normalize_text(match.group(1))
                declared_counts[current_faction] = parse_count(match.group(2)) or 0
            if not current_faction:
                continue
            for link in tr.find_all("a", href=True):
                href = str(link["href"])
                if "/site/gikai/" not in href:
                    continue
                key = profile_key(urljoin(FACTION_URL, href))
                name = normalize_text(link.get_text(" ", strip=True))
                if not name:
                    continue
                faction_by_profile[key] = current_faction
                actual_counts[current_faction] += 1
        for faction, declared in declared_counts.items():
            actual = actual_counts[faction]
            if actual != declared:
                raise RuntimeError(f"Faction {faction}: actual {actual} != declared {declared}")
        return faction_by_profile, dict(declared_counts)

    def parse_profile(self, soup: BeautifulSoup) -> dict[str, object]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            return {"kana": None, "elected_count": None, "committees": []}
        kana = None
        elected_count = None
        committees: list[str] = []
        # The kana is in the name row span; do not run a broad regex over the
        # whole profile table because contact fields also live in that table.
        for span in table.find_all("span"):
            text = normalize_text(span.get_text(" ", strip=True))
            if text and re.fullmatch(r"[ぁ-んァ-ンー\s]+", text):
                kana = text
                break
        for row in expand_table(table):
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in row]
            if len(values) < 2:
                continue
            label = values[-2]
            value = values[-1]
            if label == "当選回数":
                elected_count = parse_count(value)
            elif label == "所属委員会等":
                committees = [
                    normalize_text(item)
                    for item in re.split(r"[、,]", value)
                    if normalize_text(item)
                ]
        return {"kana": kana, "elected_count": elected_count, "committees": committees}


def main() -> int:
    scraper = YamaguchiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
