"""福井県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, link_url, make_member, out_path, capacity_from_label  # noqa: E402

COUNCIL_ID = "fukui-pref"
SOURCE_URL = "https://www.pref.fukui.lg.jp/doc/gikai-soumu/giinshokai/senkyokubetsu.html"
OUT_PATH = out_path(COUNCIL_ID)


class FukuiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        tables = soup.find_all("table")
        if len(tables) < 2:
            raise RuntimeError("district member table not found")
        members = []
        capacities = {}
        vacancies = []
        current_district = None
        for cells in expand_table(tables[1])[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 5:
                continue
            if values[0] and values[0] != "〃":
                district, capacity, _ = capacity_from_label(values[0])
                current_district = district
                capacities[district] = capacity or 0
            if "(欠員" in values[2] or "欠員" in values[2]:
                vacancies.append(
                    {"district": current_district, "ketsuin": parse_count(values[2]) or 1, "source_url": SOURCE_URL}
                )
                continue
            if not values[2] or current_district is None:
                continue
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=values[2],
                    district=current_district,
                    faction=values[3],
                    elected_count=parse_count(values[4]),
                    profile_url=link_url(cells[2], SOURCE_URL),
                )
            )

        teisu = sum(capacities.values())
        if teisu != 37:
            raise RuntimeError(f"Fukui capacity total {teisu} != 37")
        self.assert_min_count(members, 36, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="福井県議会 選挙区別名簿",
            members=members,
            teisu=teisu,
            source_basis_date="最終更新日 2026-05-19",
            vacancy_details=vacancies,
            anchor_type="official_district_capacity",
            notes=[
                "選挙区別HTMLの氏名・会派・期数のみを取得",
                "欠員行を現員から除外し、件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = FukuiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
