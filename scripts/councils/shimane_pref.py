"""島根県議会 議員一覧スクレイパー.

ソース: https://www.pref.shimane.lg.jp/gikai/gaido/meibo/tiku.html
出力: docs/data/shimane-pref/members.json
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
from scripts.lib.member_contract import apply_member_contract  # noqa: E402

COUNCIL_ID = "shimane-pref"
SOURCE_URL = "https://www.pref.shimane.lg.jp/gikai/gaido/meibo/tiku.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_DISTRICTS = 12
EXPECTED_MEMBERS = 35
EXPECTED_CAPACITY = 36
CAPACITY_IMAGE_URL = "https://www.pref.shimane.lg.jp/gikai/gaido/meibo/tiku.data/r5_senkyoku2.jpg"
DISTRICT_CAPACITIES = {
    "松江": 11,
    "浜田": 3,
    "出雲": 9,
    "益田": 2,
    "大田": 2,
    "安来": 2,
    "江津": 1,
    "雲南・飯石": 2,
    "仁多": 1,
    "邑智": 1,
    "鹿足": 1,
    "隠岐": 1,
}


class ShimanePrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        index_soup = self.fetch(SOURCE_URL)
        district_links = self.parse_district_links(index_soup)
        if len(district_links) != EXPECTED_DISTRICTS:
            raise RuntimeError(
                f"Expected {EXPECTED_DISTRICTS} district links, parsed {len(district_links)}"
            )

        members: list[dict[str, object]] = []
        district_checks: list[dict[str, object]] = []
        profile_fields_by_url: dict[str, dict[str, object]] = {}
        for district in district_links:
            soup = self.fetch(district["url"])
            district_members = self.parse_district_page(soup, district)
            for member in district_members:
                profile_url = str(member["official_profile_url"])
                profile_fields = profile_fields_by_url.get(profile_url)
                if profile_fields is None:
                    profile_fields = self.parse_profile(self.fetch(profile_url))
                    profile_fields_by_url[profile_url] = profile_fields
                if profile_fields.get("elected_count") is not None:
                    member["elected_count"] = profile_fields["elected_count"]
                committees = profile_fields.get("committees")
                if isinstance(committees, list):
                    member["committees"] = committees
            members.extend(district_members)
            capacity = DISTRICT_CAPACITIES.get(district["name"])
            if capacity is None:
                raise RuntimeError(f"{district['name']}: district capacity missing")
            vacancy = capacity - len(district_members)
            if vacancy < 0:
                raise RuntimeError(
                    f"{district['name']}: members {len(district_members)} exceeds capacity {capacity}"
                )
            district_checks.append(
                {
                    "district": district["name"],
                    "capacity": capacity,
                    "members": len(district_members),
                    "vacancies": vacancy,
                    "source_url": district["url"],
                }
            )

        ensure_unique_ids(members)
        capacity_total = sum(DISTRICT_CAPACITIES.values())
        vacancies = sum(int(item["vacancies"]) for item in district_checks)
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if vacancies != EXPECTED_CAPACITY - EXPECTED_MEMBERS:
            raise RuntimeError(f"Vacancies {vacancies} != {EXPECTED_CAPACITY - EXPECTED_MEMBERS}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "島根県議会 議員名簿（選挙区別）",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "district_pages_with_profile_allowlist",
                "capacity_source_url": CAPACITY_IMAGE_URL,
                "district_count": len(district_checks),
                "expected_district_count": EXPECTED_DISTRICTS,
                "capacity_total": capacity_total,
                "vacancies": vacancies,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "districts": district_checks,
                "notes": [
                    "選挙区別インデックスから12選挙区リンクを追従",
                    "写真altは氏名取得に使わず、氏名はリンクテキストから取得",
                    "個別プロフィールは当選回数と所属委員会のみ許可リストで取得",
                    "区別定数は公式ページ上の画像掲載のため、画像由来の定数表で件数検算",
                    "公式画像では松江は定数11・現員10。島根県全体は定数36・現員35として記録",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        vacancy_details = [
            {
                "district": district["district"],
                "ketsuin": district["vacancies"],
                "source_url": CAPACITY_IMAGE_URL,
            }
            for district in district_checks
            if int(district["vacancies"]) > 0
        ]
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date="選挙区別名簿 公式基準日記載なし / 選挙区ごとの定数画像 r5_senkyoku2.jpg",
            vacancy_details=vacancy_details,
            anchor_source_url=CAPACITY_IMAGE_URL,
            anchor_type="official_district_capacity_image",
            notes=["公式の選挙区ごとの定数画像を件数検算アンカーとして使用"],
        )
        return payload

    def parse_district_links(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        content = soup.select_one("#page-content") or soup
        links: list[dict[str, str]] = []
        seen: set[str] = set()
        for link in content.select("table a[href]"):
            name = normalize_text(link.get_text(" ", strip=True))
            href = urljoin(SOURCE_URL, str(link["href"]))
            if not name or href in seen or not href.endswith(".html"):
                continue
            seen.add(href)
            links.append({"name": name, "url": href})
        return links

    def parse_district_page(
        self,
        soup: BeautifulSoup,
        district: dict[str, str],
    ) -> list[dict[str, object]]:
        content = soup.select_one("#page-content") or soup
        members: list[dict[str, object]] = []
        for link in content.find_all("a", href=re.compile(r"/simeibetu/giin")):
            if not isinstance(link, Tag):
                continue
            cell = link.find_parent("td") or link.find_parent("p") or link.parent
            if not isinstance(cell, Tag):
                continue
            name = normalize_text(link.get_text(" ", strip=True))
            if not name:
                continue
            lines = [
                normalize_text(line)
                for line in cell.get_text("\n", strip=True).splitlines()
                if normalize_text(line)
            ]
            try:
                name_index = lines.index(name)
            except ValueError:
                name_index = 0
            kana = normalize_text(" ".join(lines[:name_index])) or None
            faction = normalize_text(lines[name_index + 1]) if name_index + 1 < len(lines) else None
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=name,
                    kana=kana,
                    district=district["name"],
                    faction=faction,
                    elected_count=None,
                        profile_url=urljoin(district["url"], str(link["href"])),
                    )
                )
        if not members:
            raise RuntimeError(f"{district['name']}: member links not found")
        return members

    def parse_profile(self, soup: BeautifulSoup) -> dict[str, object]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            return {"elected_count": None, "committees": []}
        elected_count = None
        committees: list[str] = []
        for row in expand_table(table):
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in row]
            if len(values) < 3:
                continue
            label = values[-2]
            value = values[-1]
            if label == "当選回数":
                elected_count = parse_count(value)
            elif label == "所属委員会":
                committee = normalize_text(value)
                if committee and committee not in {"-", "ｰ", "ー"} and committee not in committees:
                    committees.append(committee)
        return {"elected_count": elected_count, "committees": committees}


def main() -> int:
    scraper = ShimanePrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
