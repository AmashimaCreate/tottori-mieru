"""山梨県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, link_url, make_member, out_path  # noqa: E402

COUNCIL_ID = "yamanashi-pref"
SOURCE_URL = "https://www.pref.yamanashi.jp/gikaisom/senkyokubetu_meibo.html"
OUT_PATH = out_path(COUNCIL_ID)


class YamanashiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        table = soup.find("table")
        if table is None:
            raise RuntimeError("member table not found")
        members = []
        vacancies = []
        for cells in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 6:
                continue
            district = values[0]
            name_text = values[2]
            if not name_text:
                vacancies.append({"district": district, "ketsuin": 1, "source_url": SOURCE_URL})
                continue
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=name_text,
                    district=district,
                    faction=values[5],
                    elected_count=parse_count(values[3]),
                    profile_url=link_url(cells[2], SOURCE_URL),
                )
            )

        self.assert_min_count(members, 36, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="山梨県議会 選挙区別議員一覧",
            members=members,
            teisu=37,
            source_basis_date="更新日 2026-05-19 / 議員定数37人・欠員1名",
            vacancy_details=vacancies,
            anchor_type="official_roster_count_with_vacancy_row",
            notes=[
                "選挙区別HTMLの氏名・会派・当選回数のみを取得",
                "所在地欄は読まず、空の欠員行を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = YamanashiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
