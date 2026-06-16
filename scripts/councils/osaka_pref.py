"""大阪府議会 議員一覧スクレイパー.

ソース: https://www.pref.osaka.lg.jp/o170010/gikai_somu/sugatami20/index50.html
出力: docs/data/osaka-pref/members.json
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    ensure_unique_ids,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "osaka-pref"
SOURCE_URL = "https://www.pref.osaka.lg.jp/o170010/gikai_somu/sugatami20/index50.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_MEMBERS = 79
SOURCE_BASIS_DATE = "令和8年3月3日現在 / 更新日 2026-03-06"


class OsakaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        members = self.parse_roster(soup)
        ensure_unique_ids(members)
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "第20期大阪府議会議員一覧 五十音順",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_roster_table",
                "capacity_total": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "notes": [
                    "第20期大阪府議会議員一覧 五十音順の氏名・ふりがな・会派・選挙区のみを取得",
                    "当選回数は一覧に無いためnull",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=EXPECTED_MEMBERS,
            source_basis_date=SOURCE_BASIS_DATE,
            anchor_source_url=SOURCE_URL,
            anchor_type="official_roster_count",
            notes=["公式HTMLの五十音順一覧79人を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup) -> list[dict[str, object]]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError("Osaka roster table not found")
        members: list[dict[str, object]] = []
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 4:
                continue
            link = cells[0].find("a", href=True)
            if not isinstance(link, Tag):
                continue
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=cells[1].get_text(" ", strip=True),
                    kana=cells[0].get_text(" ", strip=True),
                    district=cells[3].get_text(" ", strip=True),
                    faction=cells[2].get_text(" ", strip=True),
                    elected_count=None,
                    profile_url=urljoin(SOURCE_URL, str(link["href"])),
                )
            )
        return members


def main() -> int:
    scraper = OsakaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
