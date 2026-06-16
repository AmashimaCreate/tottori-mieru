"""新潟県議会 議員名簿スクレイパー."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import (  # noqa: E402
    build_payload,
    link_url,
    make_member,
    out_path,
)

COUNCIL_ID = "niigata-pref"
SOURCE_URL = "https://www.pref.niigata.lg.jp/site/gikai/1356810287682.html"
DISTRICT_URL = "https://www.pref.niigata.lg.jp/site/gikai/list31-55.html"
OUT_PATH = out_path(COUNCIL_ID)


class NiigataPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        district_soup = self.fetch(DISTRICT_URL)
        table = soup.find("table")
        if table is None:
            raise RuntimeError("member table not found")

        members = []
        for cells in expand_table(table):
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 4 or values[0] == "氏名":
                continue
            profile_url = link_url(cells[0], SOURCE_URL)
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=values[0],
                    district=values[1],
                    faction=values[2],
                    elected_count=parse_count(values[3]),
                    profile_url=profile_url,
                )
            )

        teisu, vacancies = self.district_check(district_soup)
        self.assert_min_count(members, 50, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="新潟県議会 議員名簿",
            members=members,
            teisu=teisu,
            source_basis_date="更新日 2026-05-14 / 定数53人・現員52人",
            vacancy_details=vacancies,
            anchor_source_url=DISTRICT_URL,
            anchor_type="official_district_capacity_listing",
            notes=[
                "議員名簿HTMLの氏名・選挙区・会派・当選回数のみを取得",
                "選挙区別一覧の定数・現員表記を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def district_check(self, soup) -> tuple[int, list[dict]]:
        total = 0
        vacancies = []
        seen = set()
        pattern = re.compile(
            r"(.+?)選挙区[（(]定数([0-9０-９]+)人(?:・現員([0-9０-９]+)人)?[）)]"
        )
        for link in soup.find_all("a", href=True):
            text = normalize_text(link.get_text(" ", strip=True))
            match = pattern.fullmatch(text)
            if not match:
                continue
            district = match.group(1)
            if district in seen:
                continue
            seen.add(district)
            capacity = parse_count(match.group(2)) or 0
            current = parse_count(match.group(3)) if match.group(3) else capacity
            total += capacity
            if current is not None and current < capacity:
                vacancies.append(
                    {
                        "district": district,
                        "ketsuin": capacity - current,
                        "source_url": DISTRICT_URL,
                    }
                )
        if total != 53:
            raise RuntimeError(f"Niigata capacity total {total} != 53")
        return total, vacancies


def main() -> int:
    scraper = NiigataPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
