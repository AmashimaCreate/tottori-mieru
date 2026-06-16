"""静岡県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, make_member, out_path  # noqa: E402

COUNCIL_ID = "shizuoka-pref"
SOURCE_URL = "https://www.pref.shizuoka.jp/kensei/kengikai/giinshokai/1054942.html"
OUT_PATH = out_path(COUNCIL_ID)


class ShizuokaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        table = soup.find("table")
        if table is None:
            raise RuntimeError("member table not found")
        rows = expand_table(table)
        headers = [normalize_text(cell.get_text(" ", strip=True)) for cell in rows[0]]
        members = []
        teisu = 0
        genin_anchor = 0
        for cells in rows[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if not values or values[0] == "計":
                continue
            district = values[0]
            teisu += parse_count(values[1]) or 0
            genin_anchor += parse_count(values[2]) or 0
            for index, cell in enumerate(cells[3:], start=3):
                faction = headers[index] if index < len(headers) else None
                for link in cell.find_all("a", href=True):
                    name = normalize_text(link.get_text(" ", strip=True))
                    if not name:
                        continue
                    members.append(
                        make_member(
                            council_id=COUNCIL_ID,
                            name_text=name,
                            district=district,
                            faction=faction,
                            elected_count=None,
                            profile_url=urljoin(SOURCE_URL, str(link["href"])),
                        )
                    )

        if teisu != 68 or genin_anchor != 68:
            raise RuntimeError(f"Shizuoka count check failed: teisu={teisu} genin={genin_anchor}")
        self.assert_min_count(members, 68, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="静岡県議会 選挙区・会派別議員一覧",
            members=members,
            teisu=teisu,
            source_basis_date="更新日 2026-04-01",
            vacancy_details=[],
            anchor_type="official_district_capacity",
            notes=[
                "選挙区・会派別HTMLの氏名・選挙区・会派のみを取得",
                "表の定数・現員計を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = ShizuokaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
