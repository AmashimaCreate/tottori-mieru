"""石川県議会 議員名簿スクレイパー."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import expand_table, normalize_text, parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.chubu_common import build_payload, make_member, out_path, parse_name_kana  # noqa: E402

COUNCIL_ID = "ishikawa-pref"
SOURCE_URL = "https://www.pref.ishikawa.lg.jp/gikai/meibo/20150430.html"
ANCHOR_URL = "https://www.pref.ishikawa.lg.jp/gikai/meibo/senkyoku20150430.html"
OUT_PATH = out_path(COUNCIL_ID)


class IshikawaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        profile_soup = self.fetch(SOURCE_URL)
        anchor_soup = self.fetch(ANCHOR_URL)
        kana_by_name = self.kana_map(profile_soup)
        table = anchor_soup.find("table")
        if table is None:
            raise RuntimeError("district table not found")

        members = []
        capacities = {}
        for cells in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if len(values) < 5 or not values[2]:
                continue
            district, capacity, current = self.parse_district(values[0])
            capacities[district] = (capacity, current)
            committees = [normalize_text(values[4])] if values[4] else []
            members.append(
                make_member(
                    council_id=COUNCIL_ID,
                    name_text=f"{values[2]} {kana_by_name.get(values[2], '')}".strip(),
                    district=district,
                    faction=values[3],
                    elected_count=parse_count(values[1]),
                    profile_url=None,
                    committees=committees,
                )
            )

        teisu = sum(capacity for capacity, _ in capacities.values())
        vacancies = [
            {"district": district, "ketsuin": capacity - current, "source_url": ANCHOR_URL}
            for district, (capacity, current) in capacities.items()
            if current < capacity
        ]
        if teisu != 41:
            raise RuntimeError(f"Ishikawa capacity total {teisu} != 41")
        self.assert_min_count(members, 40, "members")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="石川県議会 全議員紹介 / 選挙区別名簿",
            members=members,
            teisu=teisu,
            source_basis_date="令和8年4月1日現在 / 選挙区別名簿 更新日 2026-03-02",
            vacancy_details=vacancies,
            anchor_source_url=ANCHOR_URL,
            anchor_type="official_district_capacity",
            notes=[
                "選挙区別HTMLの氏名・会派・期数・委員会のみを取得",
                "全議員紹介HTMLは氏名ふりがなの照合にのみ使用",
                "許可リスト外の個人向け項目は保存しない",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def kana_map(self, soup) -> dict[str, str]:
        mapping = {}
        for table in soup.find_all("table"):
            for cells in expand_table(table):
                values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
                if len(values) >= 3 and values[1] == "氏名":
                    name, kana, _ = parse_name_kana(values[2])
                    if name and kana:
                        mapping[name] = kana
        return mapping

    def parse_district(self, text: str) -> tuple[str, int, int]:
        value = normalize_text(text)
        district = re.split(r"[（(]", value, maxsplit=1)[0].strip()
        cap_match = re.search(r"[（(]([0-9０-９]+)人[）)]", value)
        cur_match = re.search(r"現員([0-9０-９]+)人", value)
        capacity = parse_count(cap_match.group(1)) if cap_match else None
        current = parse_count(cur_match.group(1)) if cur_match else capacity
        if capacity is None or current is None:
            raise RuntimeError(f"cannot parse district capacity: {text}")
        return district, capacity, current


def main() -> int:
    scraper = IshikawaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
