"""長野県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    compact_kana_text,
    expand_table,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, link_url, out_path  # noqa: E402

COUNCIL_ID = "nagano-pref"
SOURCE_URL = "https://www.pref.nagano.lg.jp/gikai/gikai/giin/senkyoku/index.html"
OUT_PATH = out_path(COUNCIL_ID)
PLACEHOLDER_NAMES = {"-", "ー", "－", "―", "−"}


class NaganoPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        table = soup.find_all("table")[-1]
        members = []
        capacities = {}
        member_counts = {}
        seen = set()
        for cells in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 6 or not values[2]:
                continue
            district = values[0]
            capacity = parse_count(values[1]) or 0
            capacities[district] = capacity
            if values[2] in PLACEHOLDER_NAMES:
                continue
            profile_url = link_url(cells[2], SOURCE_URL)
            key = (district, values[2], profile_url)
            if key in seen:
                continue
            seen.add(key)
            member_counts[district] = member_counts.get(district, 0) + 1
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=values[2],
                    kana=compact_kana_text(values[3]),
                    district=district,
                    faction=values[5],
                    elected_count=None,
                    profile_url=profile_url,
                )
            )

        teisu = sum(capacities.values())
        if teisu != 57:
            raise RuntimeError(f"Nagano capacity total {teisu} != 57")
        vacancy_details = []
        for district, capacity in capacities.items():
            vacancies = capacity - member_counts.get(district, 0)
            if vacancies < 0:
                raise RuntimeError(f"{district}: member count exceeds capacity")
            if vacancies:
                vacancy_details.append(
                    {"district": district, "ketsuin": vacancies, "source_url": SOURCE_URL}
                )
        if len(members) + sum(item["ketsuin"] for item in vacancy_details) != teisu:
            raise RuntimeError("Nagano member and vacancy total does not match capacity")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="長野県議会 選挙区別議員名簿",
            members=members,
            teisu=teisu,
            source_basis_date="更新日 2026-04-06 / 任期 2023-04-30〜2027-04-29",
            vacancy_details=vacancy_details,
            anchor_type="official_district_capacity",
            notes=[
                "選挙区別HTMLの氏名・ふりがな・会派のみを取得",
                "氏名欄がーの行は欠員プレースホルダとして扱い、議員データには含めない",
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
