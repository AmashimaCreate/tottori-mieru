"東京都議会 議員名簿スクレイパー."""

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
    committee_list,
    member,
    out_path,
    parse_district_capacity,
    split_name_kana,
)

COUNCIL_ID = "tokyo-pref"
SOURCE_URL = "https://www.gikai.metro.tokyo.lg.jp/membership/electoral-zone.html"
OUT_PATH = out_path(COUNCIL_ID)


class TokyoPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        entries, capacities, vacancies = self.parse_index(soup)
        members = []
        for entry in entries:
            profile = self.parse_profile(self.fetch(entry["profile_url"]))
            name = profile.get("name") or entry["name"]
            kana = profile.get("kana")
            members.append(
                member(
                    council_id=COUNCIL_ID,
                    name=name,
                    kana=kana,
                    district=entry["district"],
                    faction=profile.get("faction") or entry.get("faction"),
                    elected_count=profile.get("elected_count"),
                    profile_url=entry["profile_url"],
                    committees=profile.get("committees", []),
                )
            )

        teisu = sum(capacities.values())
        if teisu != 127:
            raise RuntimeError(f"Tokyo capacity total {teisu} != 127")
        if len(members) != 124:
            raise RuntimeError(f"Tokyo parsed members {len(members)} != 124")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="東京都議会 選挙区別議員名簿",
            members=members,
            teisu=teisu,
            source_basis_date="公式基準日記載なし / 選挙区別HTML 定数127・現員124",
            vacancy_details=vacancies,
            checks={
                "source_shape": "single_page_roster_with_profile_allowlist",
                "district_count": len(capacities),
                "district_capacities": capacities,
            },
            notes=[
                "選挙区別HTMLのリンクを起点に個別プロフィールを巡回",
                "個別プロフィールは会派・期数・所属委員会・選挙区のみ許可リストで取得",
                "連絡先・住所・電話・個人サイトは取得しない",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def parse_index(self, soup: BeautifulSoup) -> tuple[list[dict], dict[str, int], list[dict]]:
        entries: list[dict] = []
        capacities: dict[str, int] = {}
        vacancies: list[dict] = []
        for heading in soup.find_all("h4"):
            label = clean(heading.get_text(" ", strip=True))
            district, capacity, _ = parse_district_capacity(label)
            if not district or capacity is None:
                continue
            capacities[district] = capacity
            ul = heading.find_next_sibling("ul")
            links = ul.find_all("a", href=True) if isinstance(ul, Tag) else []
            current = 0
            for link in links:
                text = clean(link.get_text(" ", strip=True))
                match = re.match(r"(.+?)[（(](.+)[）)]$", text)
                name = match.group(1) if match else text
                faction = match.group(2) if match else None
                entries.append(
                    {
                        "name": clean(name),
                        "faction": clean(faction) if faction else None,
                        "district": district,
                        "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                    }
                )
                current += 1
            if current < capacity:
                vacancies.append({"district": district, "ketsuin": capacity - current, "source_url": SOURCE_URL})
        return entries, capacities, vacancies

    def parse_profile(self, soup: BeautifulSoup) -> dict:
        result = {"name": None, "kana": None, "faction": None, "elected_count": None, "committees": []}
        heading = soup.find("h3")
        if isinstance(heading, Tag):
            name, kana = split_name_kana(heading.get_text(" ", strip=True))
            result["name"] = name
            result["kana"] = kana
        table = soup.select_one(".profile table") or soup.find("table")
        if not isinstance(table, Tag):
            return result
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            label = clean(cells[0].get_text(" ", strip=True))
            value = clean(cells[1].get_text("\n", strip=True))
            if label == "会派":
                result["faction"] = value
            elif label == "期数":
                result["elected_count"] = parse_count(value)
            elif label == "所属委員会":
                result["committees"] = committee_list(value)
        return result


def main() -> int:
    scraper = TokyoPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
