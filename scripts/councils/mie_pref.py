"""三重県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, link_url, make_member, out_path  # noqa: E402

COUNCIL_ID = "mie-pref"
SOURCE_URL = "https://www.pref.mie.lg.jp/KENGIKAI/89263000001_00001.htm"
OUT_PATH = out_path(COUNCIL_ID)


class MiePrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        table = soup.find_all("table")[-1]
        members = []
        for cells in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 6 or not values[1]:
                continue
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=f"{values[1]} {values[2]}",
                    district=values[4],
                    faction=values[3],
                    elected_count=parse_count(values[5]),
                    profile_url=link_url(cells[1], SOURCE_URL),
                )
            )

        self.assert_min_count(members, 47, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="三重県議会 議員の紹介",
            members=members,
            teisu=48,
            source_basis_date="令和7年11月18日現在",
            vacancy_details=[{"district": "鈴鹿市", "ketsuin": 1, "source_url": SOURCE_URL}],
            anchor_type="official_roster_count_with_note",
            notes=[
                "議員名簿HTMLの氏名・ふりがな・会派・選挙区・期数のみを取得",
                "公式注記の鈴鹿市選挙区1名欠員を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = MiePrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
