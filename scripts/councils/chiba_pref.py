"千葉県議会 議員名簿スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.kanto_common import (  # noqa: E402
    build_payload,
    clean,
    committee_list,
    member,
    out_path,
    split_name_kana,
)

COUNCIL_ID = "chiba-pref"
SOURCE_URL = "https://www.pref.chiba.lg.jp/gikai/giji/giin/giinshoukai/index.html"
CAPACITY_URL = "https://www.pref.chiba.lg.jp/gikai/soumu/giin/senkyoku.html"
OUT_PATH = out_path(COUNCIL_ID)
EXPECTED_VACANCY_DISTRICTS = {
    "船橋市",
    "松戸市",
    "勝浦市・いすみ市・夷隅郡",
    "流山市",
    "鎌ケ谷市",
    "山武市・山武郡",
}


class ChibaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        profile_urls = self.parse_profile_urls(soup)
        members = []
        district_counts: dict[str, int] = {}
        for url in profile_urls:
            profile = self.parse_profile(self.fetch(url), url)
            district = profile["district"]
            district_counts[district] = district_counts.get(district, 0) + 1
            members.append(
                member(
                    council_id=COUNCIL_ID,
                    name=profile["name"],
                    kana=profile.get("kana"),
                    district=district,
                    faction=profile.get("faction"),
                    elected_count=profile.get("elected_count"),
                    profile_url=url,
                    committees=profile.get("committees", []),
                )
            )
        capacities = self.parse_capacities(self.fetch(CAPACITY_URL))
        vacancies = []
        for district, capacity in capacities.items():
            current = district_counts.get(district, 0)
            if current < capacity:
                vacancies.append({"district": district, "ketsuin": capacity - current, "source_url": CAPACITY_URL})
            elif current > capacity:
                raise RuntimeError(f"Chiba {district}: current {current} exceeds capacity {capacity}")
        teisu = sum(capacities.values())
        if teisu != 95:
            raise RuntimeError(f"Chiba capacity total {teisu} != 95")
        if len(members) != 89:
            raise RuntimeError(f"Chiba parsed members {len(members)} != 89")
        actual = {item["district"] for item in vacancies}
        if actual != EXPECTED_VACANCY_DISTRICTS:
            raise RuntimeError(f"Chiba vacancy mismatch: {sorted(actual)}")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="千葉県議会 議員紹介（五十音順）",
            members=members,
            teisu=teisu,
            source_basis_date="公式基準日記載なし / 選挙区及び議員定数HTML 定数95・プロフィール現員89",
            vacancy_details=vacancies,
            anchor_source_url=CAPACITY_URL,
            checks={
                "source_shape": "profile_roster_with_capacity_table",
                "capacity_source_url": CAPACITY_URL,
                "district_count": len(capacities),
                "capacity_total": teisu,
            },
            notes=[
                "五十音順HTMLから個別プロフィールURLを取得",
                "個別プロフィールは氏名・会派・選挙区・期数・所属委員会のみ許可リストで取得",
                "連絡先欄は取得しない",
                "写真は取得せず、photo_urlは全員null",
            ],
        )

    def parse_profile_urls(self, soup: BeautifulSoup) -> list[str]:
        urls = []
        seen = set()
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if "/gikai/soumu/giin/giinshoukai/giin-" not in href:
                continue
            url = urljoin(SOURCE_URL, href)
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    def parse_profile(self, soup: BeautifulSoup, url: str) -> dict:
        fields: dict[str, object] = {"committees": []}
        table = soup.find("table")
        if not isinstance(table, Tag):
            raise RuntimeError(f"{url}: profile table not found")
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            label = clean(cells[0].get_text(" ", strip=True))
            value = clean(cells[1].get_text("\n", strip=True))
            if label == "氏名":
                name, kana = split_name_kana(value)
                fields["name"] = name
                fields["kana"] = kana
            elif label == "所属会派等":
                fields["faction"] = value
            elif label == "選挙区":
                fields["district"] = value
            elif label == "期数":
                fields["elected_count"] = parse_count(value)
            elif label == "所属委員会":
                fields["committees"] = committee_list(value)
        for key in ("name", "district"):
            if key not in fields:
                raise RuntimeError(f"{url}: missing {key}")
        return fields

    def parse_capacities(self, soup: BeautifulSoup) -> dict[str, int]:
        capacities: dict[str, int] = {}
        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            name = clean(cells[0].get_text(" ", strip=True))
            count = parse_count(cells[1].get_text(" ", strip=True))
            if name and count is not None and name != "選挙区名":
                capacities[name] = count
        return capacities


def main() -> int:
    scraper = ChibaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
