"群馬県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.kanto_common import build_payload, clean, committee_list, member, out_path, parse_district_capacity  # noqa: E402

COUNCIL_ID = "gunma-pref"
SOURCE_URL = "https://www.pref.gunma.jp/site/gikai/25704.html"
OUT_PATH = out_path(COUNCIL_ID)


class GunmaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Gunma roster table not found")
        members = []
        capacities: dict[str, int] = {}
        vacancies: list[dict] = []
        for cells in expand_table(table):
            values = [clean(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 10 or values[0].startswith("選挙区"):
                continue
            link = cells[1].find("a", href=True)
            if not isinstance(link, Tag):
                continue
            district, capacity, vacancy = parse_district_capacity(values[0])
            if district and capacity is not None and district not in capacities:
                capacities[district] = capacity
                if vacancy:
                    vacancies.append({"district": district, "ketsuin": vacancy, "source_url": SOURCE_URL})
            committees = committee_list(values[5], values[6], values[7], values[8], values[9])
            members.append(
                member(
                    council_id=COUNCIL_ID,
                    name=values[1],
                    kana=values[2],
                    district=district,
                    faction=values[4],
                    elected_count=parse_count(values[3]),
                    profile_url=urljoin(SOURCE_URL, str(link["href"])),
                    committees=committees,
                )
            )
        teisu = sum(capacities.values())
        if teisu != 50:
            raise RuntimeError(f"Gunma capacity total {teisu} != 50")
        if len(members) != 46:
            raise RuntimeError(f"Gunma parsed members {len(members)} != 46")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="群馬県議会 議員の紹介 選挙区別",
            members=members,
            teisu=teisu,
            source_basis_date="公式基準日記載なし / 選挙区別HTML 定数50・現員46",
            vacancy_details=vacancies,
            checks={
                "source_shape": "single_page_roster_table",
                "district_count": len(capacities),
                "district_capacities": capacities,
            },
            notes=[
                "選挙区別HTMLの表から氏名・ふりがな・当選回数・会派・委員会のみを取得",
                "選挙区セルの定数・欠員表記を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = GunmaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
