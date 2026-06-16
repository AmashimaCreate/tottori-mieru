"""愛知県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import normalize_text  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import (  # noqa: E402
    build_payload,
    capacity_from_label,
    make_member,
    out_path,
    parse_faction_and_count,
)

COUNCIL_ID = "aichi-pref"
SOURCE_URL = "https://www.pref.aichi.jp/site/gikai/giin-senkyoku.html"
OUT_PATH = out_path(COUNCIL_ID)


class AichiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        box = soup.select_one(".detail_free")
        if box is None:
            raise RuntimeError("detail_free not found")
        children = [child for child in box.children if isinstance(child, Tag)]
        members = []
        capacities = {}
        vacancies = []
        current_district = None
        for index, child in enumerate(children):
            if child.name == "h2":
                label = normalize_text(child.get_text(" ", strip=True))
                district, capacity, vacancy = capacity_from_label(label)
                current_district = district
                capacities[district] = capacity or 0
                if vacancy:
                    vacancies.append({"district": district, "ketsuin": vacancy, "source_url": SOURCE_URL})
                continue
            if child.name != "p" or current_district is None:
                continue
            text = normalize_text(child.get_text("\n", strip=True))
            if "当選" not in text or "プロフィール" in text:
                continue
            lines = [normalize_text(line) for line in child.get_text("\n", strip=True).splitlines() if normalize_text(line)]
            if len(lines) < 2:
                continue
            faction, elected_count = parse_faction_and_count(lines[-1])
            profile_url = self.next_profile_url(children, index)
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=lines[0],
                    district=current_district,
                    faction=faction,
                    elected_count=elected_count,
                    profile_url=profile_url,
                )
            )

        teisu = sum(capacities.values())
        if teisu != 102:
            raise RuntimeError(f"Aichi capacity total {teisu} != 102")
        self.assert_min_count(members, 97, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="愛知県議会 選挙区別議員一覧",
            members=members,
            teisu=teisu,
            source_basis_date="公式基準日記載なし / 定数102人・現員97人",
            vacancy_details=vacancies,
            anchor_type="official_district_capacity",
            notes=[
                "選挙区別HTMLの人物カードから氏名・ふりがな・会派・当選回数のみを取得",
                "各選挙区見出しの定数・欠員表記を件数検算アンカーとして使用",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def next_profile_url(self, children: list[Tag], index: int) -> str | None:
        for child in children[index + 1 :]:
            if child.name == "h2":
                return None
            link = child.find("a", href=True)
            if link and "giin-" in str(link["href"]):
                return urljoin(SOURCE_URL, str(link["href"]))
            if child.name == "p" and "当選" in normalize_text(child.get_text(" ", strip=True)):
                return None
        return None


def main() -> int:
    scraper = AichiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
