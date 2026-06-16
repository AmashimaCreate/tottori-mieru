"""富山県議会 議員名簿スクレイパー."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, link_url, make_member, out_path  # noqa: E402

COUNCIL_ID = "toyama-pref"
SOURCE_URL = "https://www.pref.toyama.jp/0100/gikai/members/kubetu.html"
OUT_PATH = out_path(COUNCIL_ID)


class ToyamaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        members = []
        teisu = 0
        vacancies = []
        district_re = re.compile(r"(.+?)[（(]定数([0-9０-９]+)/現員([0-9０-９]+)[）)]")
        for heading in soup.find_all("h3"):
            text = normalize_text(heading.get_text(" ", strip=True))
            match = district_re.search(text)
            if not match:
                continue
            district = match.group(1)
            capacity = parse_count(match.group(2)) or 0
            current = parse_count(match.group(3)) or 0
            teisu += capacity
            if current < capacity:
                vacancies.append(
                    {"district": district, "ketsuin": capacity - current, "source_url": SOURCE_URL}
                )
            table = heading.find_next("table")
            if not isinstance(table, Tag):
                continue
            for cells in expand_table(table)[1:]:
                values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
                if len(values) < 3 or not values[0]:
                    continue
                members.append(
                    make_member(
                        council_id=COUNCIL_ID,
                        name_text=values[0],
                        district=district,
                        faction=values[1],
                        elected_count=parse_count(values[2]),
                        profile_url=link_url(cells[0], SOURCE_URL),
                    )
                )

        if teisu != 40:
            raise RuntimeError(f"Toyama capacity total {teisu} != 40")
        self.assert_min_count(members, 40, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="富山県議会 選挙区別議員名簿",
            members=members,
            teisu=teisu,
            source_basis_date="更新日 2025-04-22",
            vacancy_details=vacancies,
            anchor_type="official_district_capacity",
            notes=[
                "選挙区別HTMLの氏名・会派・当選回数のみを取得",
                "各選挙区見出しの定数・現員表記を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = ToyamaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
