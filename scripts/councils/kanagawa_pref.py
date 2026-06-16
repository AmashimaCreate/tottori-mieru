"神奈川県議会 議員名簿スクレイパー."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.kanto_common import (  # noqa: E402
    build_payload,
    clean,
    member,
    out_path,
    parse_district_capacity,
)

COUNCIL_ID = "kanagawa-pref"
SOURCE_URL = "https://www.pref.kanagawa.jp/gikai/p80275.html"
FACTION_URL = "https://www.pref.kanagawa.jp/gikai/p307827.html"
COMMITTEE_URL = "https://www.pref.kanagawa.jp/gikai/p308696.html"
OUT_PATH = out_path(COUNCIL_ID)
EXPECTED_VACANCIES = {
    "横浜市神奈川区",
    "川崎市中原区",
    "川崎市宮前区",
    "鎌倉市",
    "小田原市",
    "茅ヶ崎市",
}


class KanagawaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        faction_by_url = self.parse_factions(self.fetch(FACTION_URL))
        committees_by_url = self.parse_committees(self.fetch(COMMITTEE_URL))
        entries, capacities, vacancies = self.parse_index(soup)
        members = [
            member(
                council_id=COUNCIL_ID,
                name=entry["name"],
                kana=entry["kana"],
                district=entry["district"],
                faction=faction_by_url.get(entry["profile_url"]),
                elected_count=None,
                profile_url=entry["profile_url"],
                committees=committees_by_url.get(entry["profile_url"], []),
            )
            for entry in entries
        ]
        teisu = sum(capacities.values())
        if teisu != 105:
            raise RuntimeError(f"Kanagawa capacity total {teisu} != 105")
        if len(members) != 99:
            raise RuntimeError(f"Kanagawa parsed members {len(members)} != 99")
        actual_vacant = {item["district"] for item in vacancies}
        if actual_vacant != EXPECTED_VACANCIES:
            raise RuntimeError(f"Kanagawa vacancy mismatch: {sorted(actual_vacant)}")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="神奈川県議会 議員の紹介 選挙区でさがす",
            members=members,
            teisu=teisu,
            source_basis_date="公式基準日記載なし / 会派別HTML 定数105・現員99",
            vacancy_details=vacancies,
            checks={
                "source_shape": "single_page_roster_multi_view",
                "district_count": len(capacities),
                "faction_source_url": FACTION_URL,
                "committee_source_url": COMMITTEE_URL,
            },
            notes=[
                "選挙区別HTMLから氏名・ふりがな・選挙区を取得",
                "会派別HTMLをプロフィールURLキーで結合",
                "委員会別HTMLをプロフィールURLキーで結合",
                "当選回数は公式HTMLに見当たらないためnull",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def parse_index(self, soup: BeautifulSoup) -> tuple[list[dict], dict[str, int], list[dict]]:
        entries: list[dict] = []
        capacities: dict[str, int] = {}
        vacancies: list[dict] = []
        for heading in soup.find_all("h2"):
            district, capacity, _ = parse_district_capacity(heading.get_text(" ", strip=True))
            district = re.sub(r"\s*定数\d+人\s*$", "", district)
            if not district or capacity is None:
                continue
            capacities[district] = capacity
            table = heading.find_next_sibling("table")
            if not isinstance(table, Tag):
                continue
            current = 0
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"], recursive=False)
                if len(cells) < 2:
                    continue
                link = cells[0].find("a", href=True)
                if not isinstance(link, Tag):
                    continue
                entries.append(
                    {
                        "name": clean(link.get_text(" ", strip=True)),
                        "kana": clean(cells[1].get_text(" ", strip=True)),
                        "district": district,
                        "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                    }
                )
                current += 1
            if current < capacity:
                vacancies.append({"district": district, "ketsuin": capacity - current, "source_url": SOURCE_URL})
        return entries, capacities, vacancies

    def parse_factions(self, soup: BeautifulSoup) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for heading in soup.find_all("h3"):
            faction = clean(heading.get_text(" ", strip=True))
            table = heading.find_next_sibling("table")
            if not faction or not isinstance(table, Tag):
                continue
            for link in table.find_all("a", href=True):
                mapping[urljoin(FACTION_URL, str(link["href"]))] = faction
        return mapping

    def parse_committees(self, soup: BeautifulSoup) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        current_committee: str | None = None
        for node in soup.select("h2, table"):
            if node.name == "h2":
                current_committee = clean(node.get_text(" ", strip=True))
                continue
            if node.name != "table" or not current_committee:
                continue
            for row in node.find_all("tr"):
                cells = row.find_all(["td", "th"], recursive=False)
                if len(cells) < 2:
                    continue
                link = cells[1].find("a", href=True)
                if not isinstance(link, Tag):
                    continue
                url = urljoin(COMMITTEE_URL, str(link["href"]))
                mapping.setdefault(url, [])
                if current_committee not in mapping[url]:
                    mapping[url].append(current_committee)
        return mapping


def main() -> int:
    scraper = KanagawaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
