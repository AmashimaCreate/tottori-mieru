"""岐阜県議会 議員名簿スクレイパー."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, link_url, make_member, out_path  # noqa: E402

COUNCIL_ID = "gifu-pref"
SOURCE_URL = "https://www.pref.gifu.lg.jp/site/gikai/13309.html"
DISTRICT_URL = "https://www.pref.gifu.lg.jp/site/gikai/13310.html"
OUT_PATH = out_path(COUNCIL_ID)


class GifuPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        district_soup = self.fetch(DISTRICT_URL)
        table = soup.find("table")
        if table is None:
            raise RuntimeError("member table not found")
        members = []
        for cells in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 5 or not values[1]:
                continue
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=f"{values[1]} {values[2]}",
                    district=values[3],
                    faction=values[4],
                    elected_count=None,
                    profile_url=link_url(cells[1], SOURCE_URL),
                )
            )

        teisu, vacancies = self.district_check(district_soup)
        self.assert_min_count(members, 45, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="岐阜県議会 議員一覧",
            members=members,
            teisu=teisu,
            source_basis_date="令和8年3月10日現在",
            vacancy_details=vacancies,
            anchor_source_url=DISTRICT_URL,
            anchor_type="official_district_capacity",
            notes=[
                "議員一覧HTMLの氏名・ふりがな・選挙区・会派のみを取得",
                "選挙区別一覧の定数と現員行数を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def district_check(self, soup) -> tuple[int, list[dict]]:
        capacities = {}
        names_by_district = {}
        for table in soup.find_all("table"):
            for cells in expand_table(table)[1:]:
                values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
                if len(values) < 3:
                    continue
                match = re.search(r"(.+?)\s*定数\s*([0-9０-９]+)", values[0])
                if not match:
                    continue
                district = match.group(1)
                capacities[district] = parse_count(match.group(2)) or 0
                if values[1]:
                    names_by_district.setdefault(district, set()).add(values[1])
        total = sum(capacities.values())
        if total != 46:
            raise RuntimeError(f"Gifu capacity total {total} != 46")
        vacancies = []
        for district, capacity in capacities.items():
            current = len(names_by_district.get(district, set()))
            if current < capacity:
                vacancies.append(
                    {"district": district, "ketsuin": capacity - current, "source_url": DISTRICT_URL}
                )
        return total, vacancies


def main() -> int:
    scraper = GifuPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
