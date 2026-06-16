"""福島県議会 議員一覧スクレイパー."""

from __future__ import annotations

import re
import sys
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
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "fukushima-pref"
SOURCE_URL = "https://www.pref.fukushima.lg.jp/site/gikai/meibo-senkyoku2020.html"
TERM_URL = "https://www.pref.fukushima.lg.jp/site/gikai/meibo-kaiha201712.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 58


def profile_key(url: str) -> str:
    return urlparse(url).path


def split_district_capacity(value: str) -> tuple[str, int] | None:
    text = normalize_text(value)
    match = re.search(r"(.+?)[（(]\s*定数\s*([0-9０-９]+)\s*[)）]", text)
    if not match:
        return None
    return normalize_text(match.group(1)), parse_count(match.group(2)) or 0


def canonical_faction(value: str) -> str:
    text = normalize_text(value)
    aliases = {
        "福島県議会県民連合議員会": "県民連合",
        "自由民主党福島県議会議員会": "自由民主党",
        "公明党福島県議会議員団": "公明党",
        "日本共産党福島県議会議員団": "日本共産党",
        "日本維新・無所属の会": "日本維新・無所属の会",
    }
    return aliases.get(text, text)


class FukushimaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        roster_soup = self.fetch(SOURCE_URL)
        term_soup = self.fetch(TERM_URL)
        term_data = self.parse_term_page(term_soup)
        roster_rows, district_checks = self.parse_roster(roster_soup)
        members: list[dict[str, object]] = []
        missing_terms: list[str] = []
        faction_mismatches: list[str] = []
        for row in roster_rows:
            key = profile_key(str(row["profile_url"]))
            term = term_data.get(key)
            if term is None:
                missing_terms.append(f"{row['name']} {key}")
                elected_count = None
            else:
                elected_count = term["elected_count"]
                if canonical_faction(str(term["faction"])) != canonical_faction(str(row["faction"])):
                    faction_mismatches.append(
                        f"{row['name']}: roster={row['faction']} term={term['faction']}"
                    )
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=str(row["name"]),
                    kana=None,
                    district=str(row["district"]),
                    faction=str(row["faction"]),
                    elected_count=elected_count,
                    profile_url=str(row["profile_url"]),
                )
            )
        if missing_terms:
            raise RuntimeError(f"Fukushima term join missing: {missing_terms}")
        if faction_mismatches:
            raise RuntimeError(f"Fukushima faction mismatches: {faction_mismatches}")

        ensure_unique_ids(members)
        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if len(term_data) != len(members):
            raise RuntimeError(f"Term page has {len(term_data)} members; roster has {len(members)}")

        vacancy_details = [
            {"district": item["district"], "ketsuin": item["vacancies"], "source_url": SOURCE_URL}
            for item in district_checks
            if int(item["vacancies"]) > 0
        ]
        payload: dict[str, object] = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "福島県議会 選挙区別名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_district_table_with_term_join",
                "term_source_url": TERM_URL,
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "parsed_members": len(members),
                "term_rows": len(term_data),
                "districts": district_checks,
                "notes": [
                    "選挙区別名簿から氏名・選挙区・会派のみを許可リスト抽出",
                    "許可リスト外の項目は保存しない",
                    "会派別・期別一覧からプロフィールURLキーで当選回数を結合",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date="掲載日: 2026年2月24日更新",
            vacancy_details=vacancy_details,
            anchor_source_url=SOURCE_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区別名簿の定数を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        table = soup.select_one(".detail_free table")
        if not isinstance(table, Tag):
            raise RuntimeError("Fukushima roster table not found")
        rows: list[dict[str, object]] = []
        checks_by_district: dict[str, dict[str, object]] = {}
        for row in expand_table(table)[1:]:
            if len(row) < 4:
                continue
            district_info = split_district_capacity(row[0].get_text(" ", strip=True))
            link = row[1].find("a", href=True)
            if district_info is None or not isinstance(link, Tag):
                continue
            district, capacity = district_info
            check = checks_by_district.setdefault(
                district,
                {
                    "district": district,
                    "capacity": capacity,
                    "members": 0,
                    "vacancies": 0,
                    "source_url": SOURCE_URL,
                },
            )
            check["members"] = int(check["members"]) + 1
            rows.append(
                {
                    "district": district,
                    "name": normalize_text(link.get_text(" ", strip=True)),
                    "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                    "faction": normalize_text(row[3].get_text(" ", strip=True)),
                }
            )
        checks: list[dict[str, object]] = []
        for check in checks_by_district.values():
            vacancy = int(check["capacity"]) - int(check["members"])
            if vacancy < 0:
                raise RuntimeError(
                    f"{check['district']}: members {check['members']} exceeds capacity {check['capacity']}"
                )
            check["vacancies"] = vacancy
            checks.append(check)
        return rows, checks

    def parse_term_page(self, soup: BeautifulSoup) -> dict[str, dict[str, object]]:
        output: dict[str, dict[str, object]] = {}
        current_faction: str | None = None
        content = soup.select_one(".detail_free") or soup
        for tag in content.find_all(["td", "p"]):
            text = normalize_text(tag.get_text(" ", strip=True))
            faction_match = re.match(r"(.+?)[（(]\s*[0-9０-９]+名\s*[)）]", text)
            if tag.name == "td" and faction_match and "期" not in faction_match.group(1):
                current_faction = normalize_text(faction_match.group(1))
                continue
            if tag.name != "p" or current_faction is None:
                continue
            term_match = re.search(r"([0-9０-９]+)\s*期", text)
            if not term_match:
                continue
            elected_count = parse_count(term_match.group(1))
            if elected_count is None:
                continue
            for link in tag.find_all("a", href=True):
                output[profile_key(urljoin(TERM_URL, str(link["href"])))] = {
                    "faction": current_faction,
                    "elected_count": elected_count,
                    "name": normalize_text(link.get_text(" ", strip=True)),
                }
        return output


def main() -> int:
    scraper = FukushimaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
