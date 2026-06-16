"""長野県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, link_url, make_member, out_path  # noqa: E402

COUNCIL_ID = "nagano-pref"
SOURCE_URL = "https://www.pref.nagano.lg.jp/gikai/gikai/giin/senkyoku/index.html"
OUT_PATH = out_path(COUNCIL_ID)


class NaganoPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        table = soup.find_all("table")[-1]
        members = []
        capacities = {}
        seen = set()
        for cells in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 6 or not values[2]:
                continue
            district = values[0]
            capacity = parse_count(values[1]) or 0
            capacities[district] = capacity
            profile_url = link_url(cells[2], SOURCE_URL)
            key = (district, values[2], profile_url)
            if key in seen:
                continue
            seen.add(key)
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=f"{values[2]} {values[3]}",
                    district=district,
                    faction=values[5],
                    elected_count=None,
                    profile_url=profile_url,
                )
            )

        teisu = sum(capacities.values())
        if teisu != 57:
            raise RuntimeError(f"Nagano capacity total {teisu} != 57")
        self.assert_min_count(members, 57, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="長野県議会 選挙区別議員名簿",
            members=members,
            teisu=teisu,
            source_basis_date="更新日 2026-04-06 / 任期 2023-04-30〜2027-04-29",
            vacancy_details=[],
            anchor_type="official_district_capacity",
            notes=[
                "選挙区別HTMLの氏名・ふりがな・会派のみを取得",
                "連絡場所列は読まず、重複表示行はプロフィールURLで除外",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = NaganoPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
