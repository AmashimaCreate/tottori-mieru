"栃木県議会 議員名簿スクレイパー."""

from __future__ import annotations

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
)

COUNCIL_ID = "tochigi-pref"
SOURCE_URL = "https://www.pref.tochigi.lg.jp/p01/assembly/giin/meibo/meibosenkyokuyobi.html"
OUT_PATH = out_path(COUNCIL_ID)


class TochigiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        entries, capacities, vacancies = self.parse_index(soup)
        members = []
        for entry in entries:
            profile = self.parse_profile(self.fetch(entry["profile_url"]), entry["profile_url"])
            members.append(
                member(
                    council_id=COUNCIL_ID,
                    name=entry["name"],
                    kana=profile.get("kana"),
                    district=entry["district"],
                    faction=profile.get("faction") or entry.get("faction"),
                    elected_count=profile.get("elected_count"),
                    profile_url=entry["profile_url"],
                    committees=profile.get("committees", []),
                )
            )
        teisu = sum(capacities.values())
        if teisu != 50:
            raise RuntimeError(f"Tochigi capacity total {teisu} != 50")
        if len(members) != 45:
            raise RuntimeError(f"Tochigi parsed members {len(members)} != 45")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="栃木県議会 選挙区別議員名簿",
            members=members,
            teisu=teisu,
            source_basis_date="令和8年4月20日現在 / 定数50・現員45",
            vacancy_details=vacancies,
            checks={
                "source_shape": "district_tables_with_profile_allowlist",
                "district_count": len(capacities),
                "district_capacities": capacities,
            },
            notes=[
                "選挙区別一覧は連絡先欄を含むため、氏名リンク・会派列のみを抽出",
                "個別プロフィールはふりがな・期数・選挙区・会派・所属委員会等のみ許可リストで取得",
                "連絡先欄・個人サイトは取得しない",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def parse_index(self, soup: BeautifulSoup) -> tuple[list[dict], dict[str, int], list[dict]]:
        entries: list[dict] = []
        capacities: dict[str, int] = {}
        vacancies: list[dict] = []
        for heading in soup.find_all("h2"):
            label = clean(heading.get_text(" ", strip=True))
            if "選挙区" not in label or "定数" not in label:
                continue
            district, capacity, vacancy = parse_district_capacity(label)
            if not district or capacity is None:
                continue
            capacities[district] = capacity
            if vacancy:
                vacancies.append({"district": district, "ketsuin": vacancy, "source_url": SOURCE_URL})
            table = heading.find_next_sibling("table")
            if not isinstance(table, Tag):
                continue
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"], recursive=False)
                if len(cells) < 4:
                    continue
                link = cells[0].find("a", href=True)
                if not isinstance(link, Tag):
                    continue
                # 連絡先欄は読まず、氏名リンクと会派列だけを使う。
                entries.append(
                    {
                        "name": clean(link.get_text(" ", strip=True)),
                        "district": district,
                        "faction": clean(cells[3].get_text(" ", strip=True)),
                        "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                    }
                )
        return entries, capacities, vacancies

    def parse_profile(self, soup: BeautifulSoup, url: str) -> dict:
        result: dict[str, object] = {"committees": []}
        table = soup.find("table", class_="tbl_data") or soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError(f"{url}: profile table not found")
        rows = table.find_all("tr")
        if rows:
            first_cells = rows[0].find_all("td", recursive=False)
            if len(first_cells) >= 2:
                result["kana"] = clean(first_cells[1].get_text(" ", strip=True))
        for row in rows:
            cells = row.find_all("td", recursive=False)
            if len(cells) < 2:
                continue
            label = clean(cells[0].get_text(" ", strip=True))
            value = clean(cells[-1].get_text("\n", strip=True))
            if label == "期数":
                result["elected_count"] = parse_count(value)
            elif label == "会派":
                result["faction"] = value
            elif label == "所属委員会等":
                result["committees"] = committee_list(value)
        return result


def main() -> int:
    scraper = TochigiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
