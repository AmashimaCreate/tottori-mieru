"埼玉県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.kanto_common import (  # noqa: E402
    build_payload,
    clean,
    member,
    out_path,
    parse_district_capacity,
    text_list,
)

COUNCIL_ID = "saitama-pref"
SOURCE_URL = "https://www.pref.saitama.lg.jp/e1601/gikai-member-senkyoku.html"
KAIHA_URL = "https://www.pref.saitama.lg.jp/e1601/gikai-member-kaiha.html"
GOJUON_URL = "https://www.pref.saitama.lg.jp/e1601/gikai-member-50on.html"
OUT_PATH = out_path(COUNCIL_ID)


class SaitamaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        district_links = self.parse_district_links(soup)
        members = []
        capacities: dict[str, int] = {}
        vacancies: list[dict] = []
        for district in district_links:
            district_soup = self.fetch(district["url"])
            district_name, capacity, vacancy, district_members = self.parse_district_page(district_soup, district["url"])
            if capacity is None:
                raise RuntimeError(f"{district['url']}: capacity not found")
            capacities[district_name] = capacity
            if vacancy:
                vacancies.append({"district": district_name, "ketsuin": vacancy, "source_url": district["url"]})
            members.extend(district_members)

        district_names = {str(item["name"]) for item in members}
        kaiha_names = self.parse_reference_names(self.fetch(KAIHA_URL), KAIHA_URL)
        gojuon_names = self.parse_reference_names(self.fetch(GOJUON_URL), GOJUON_URL)
        kaiha_only = sorted(kaiha_names - district_names)
        district_only_from_kaiha = sorted(district_names - kaiha_names)
        gojuon_only = sorted(gojuon_names - district_names)
        # 2026-06確認時点で、参照ページ側だけに残る氏名がある。
        # 現員の真値は区別ページの実掲載数とし、参照ページの片側差分は自動補完せず quality check に残す。
        if district_only_from_kaiha:
            raise RuntimeError(
                f"Saitama district members missing from kaiha reference: {district_only_from_kaiha}"
            )
        teisu = sum(capacities.values())
        if teisu != 93:
            raise RuntimeError(f"Saitama capacity total {teisu} != 93")
        if len(members) != 86:
            raise RuntimeError(f"Saitama parsed members {len(members)} != 86")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="埼玉県議会 議員名簿 選挙区別",
            members=members,
            teisu=teisu,
            source_basis_date="公式基準日記載なし / 選挙区別HTML 定数93・現員86（親ページ欠員6表記と区別実数に不整合あり）",
            vacancy_details=vacancies,
            checks={
                "source_shape": "district_split_roster_with_reference_crosscheck",
                "district_count": len(capacities),
                "district_capacities": capacities,
                "reference_pages": {
                    "kaiha": KAIHA_URL,
                    "gojuon": GOJUON_URL,
                },
                "one_sided_reference_names": {
                    "kaiha_only": kaiha_only,
                    "gojuon_only": gojuon_only,
                    "district_only_from_kaiha": district_only_from_kaiha,
                },
            },
            notes=[
                "区別ページの実掲載を現員の真値として採用",
                "公式親ページは欠員6と表示するが、区別見出しの定数・欠員は定数93・現員86・欠員7",
                "会派別・五十音順など参照ページ側だけに残る氏名はone_sided_reference_namesに保持し、自動補完しない",
                "当選回数は公式HTMLに見当たらないためnull",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def parse_district_links(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        links = []
        seen = set()
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if "/e1601/gikai-member-list/r5/" not in href:
                continue
            url = urljoin(SOURCE_URL, href)
            if url in seen:
                continue
            seen.add(url)
            links.append({"label": clean(link.get_text(" ", strip=True)), "url": url})
        if len(links) != 51:
            raise RuntimeError(f"Saitama district links {len(links)} != 51")
        return links

    def parse_district_page(self, soup: BeautifulSoup, url: str) -> tuple[str, int | None, int, list[dict]]:
        heading = next((h for h in soup.find_all("h3") if "定数" in h.get_text(" ", strip=True)), None)
        if not isinstance(heading, Tag):
            raise RuntimeError(f"{url}: roster h3 not found")
        district, capacity, vacancy = parse_district_capacity(heading.get_text(" ", strip=True))
        table = heading.find_next("table")
        if not isinstance(table, Tag):
            raise RuntimeError(f"{url}: roster table not found")
        members = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            lines = text_list(cells[1])
            if len(lines) < 3:
                continue
            committees = []
            for item in cells[1].find_all("li"):
                text = clean(item.get_text(" ", strip=True))
                if text:
                    committees.append(text)
            members.append(
                member(
                    council_id=COUNCIL_ID,
                    name=lines[0],
                    kana=lines[1],
                    district=district,
                    faction=lines[2],
                    elected_count=None,
                    profile_url=None,
                    committees=committees,
                )
            )
        return district, capacity, vacancy, members

    def parse_reference_names(self, soup: BeautifulSoup, base_url: str) -> set[str]:
        names: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if "/e1601/gikai-member-list/r5/" not in href:
                continue
            for line in text_list(link):
                name = clean(line).replace(" ", "")
                if name:
                    names.add(name)
        return names


def main() -> int:
    scraper = SaitamaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
