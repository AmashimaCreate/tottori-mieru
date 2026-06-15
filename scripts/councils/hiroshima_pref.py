"""広島県議会 議員一覧スクレイパー.

ソース: https://www.pref.hiroshima.lg.jp/site/gikai/giin-giin-mei.html
出力: docs/data/hiroshima-pref/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    ensure_unique_ids,
    expand_table,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract  # noqa: E402

COUNCIL_ID = "hiroshima-pref"
SOURCE_URL = "https://www.pref.hiroshima.lg.jp/site/gikai/giin-giin-mei.html"
SEIJI_URL = "https://www.pref.hiroshima.lg.jp/site/gikai/seiji01.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_DISTRICTS = 23
EXPECTED_CAPACITY = 64
EXPECTED_MEMBERS = 63
EXPECTED_VACANCIES = 1

FACTION_MAP = {
    "自民議連": "自由民主党広島県議会議員連盟",
    "民主県政会": "広島県議会民主県政会",
    "公明党": "公明党広島県議会議員団",
    "広志会": "自由民主党広島県議会広志会",
    "日本共産党": "日本共産党広島県議会議員団",
    "自民会": "自由民主党広島県議会議員会",
    "無所属ひとわ": "無所属ひとわ",
    "ひろしま刷新": "ひろしま、刷新。",
    "義友会": "義友会",
}

CORRECT_NAME_MAP = {
    "金口巖": "金口巖",
    "鷹廣純": "鷹廣純",
    "冨永健三": "冨永健三",
    "檜山俊宏": "檜山俊宏",
}


class HiroshimaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        members, district_checks = self.parse_roster(soup)
        profile_fields_by_url: dict[str, dict[str, object]] = {}
        for member in members:
            profile_url = str(member["official_profile_url"])
            profile_fields = profile_fields_by_url.get(profile_url)
            if profile_fields is None:
                profile_fields = self.parse_profile(self.fetch(profile_url))
                profile_fields_by_url[profile_url] = profile_fields
            if profile_fields.get("elected_count") is not None:
                member["elected_count"] = profile_fields["elected_count"]
            committees = profile_fields.get("committees")
            if isinstance(committees, list):
                member["committees"] = committees

        ensure_unique_ids(members)
        capacity_total = sum(int(d["capacity"]) for d in district_checks)
        vacancies = sum(int(d["vacancies"]) for d in district_checks)
        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"Expected {EXPECTED_DISTRICTS} districts, parsed {len(district_checks)}")
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if vacancies != EXPECTED_VACANCIES:
            raise RuntimeError(f"Vacancies {vacancies} != {EXPECTED_VACANCIES}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "広島県議会 議員名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_district_heading_list_with_profile_allowlist",
                "correct_name_source_url": SEIJI_URL,
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "vacancies": vacancies,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "districts": district_checks,
                "notes": [
                    "選挙区見出しの定数と直後の議員リンク列挙から抽出",
                    "安芸郡は定数3・現員2のため欠員1として記録",
                    "※付き氏名は公式の正字一覧画像を確認し、正字表記を保持",
                    "個別プロフィールは期数と委員会のみ許可リストで取得",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        vacancy_details = [
            {
                "district": district["district"],
                "ketsuin": district["vacancies"],
                "source_url": district["source_url"],
            }
            for district in district_checks
            if int(district["vacancies"]) > 0
        ]
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date="掲載日: 2026年3月23日",
            vacancy_details=vacancy_details,
            anchor_source_url=SOURCE_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区見出しの定数を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        content = soup.select_one(".detail_free") or soup
        members: list[dict[str, object]] = []
        district_checks: list[dict[str, object]] = []
        for heading in content.find_all("h4"):
            label = normalize_text(heading.get_text(" ", strip=True))
            match = re.match(r"(.+?)\s*[（(]\s*定数[:：]\s*([0-9０-９]+)\s*名", label)
            if not match:
                continue
            district = normalize_text(match.group(1))
            capacity = parse_count(match.group(2)) or 0
            paragraph = heading.find_next_sibling("p")
            district_members: list[dict[str, object]] = []
            if isinstance(paragraph, Tag):
                for link in paragraph.find_all("a", href=re.compile(r"giin-giinprof")):
                    name = self.correct_name(normalize_text(link.get_text(" ", strip=True)))
                    faction = self.faction_after_link(link)
                    district_members.append(
                        build_member(
                            council_id=COUNCIL_ID,
                            name=name,
                            kana=None,
                            district=district,
                            faction=faction,
                            elected_count=None,
                            profile_url=urljoin(SOURCE_URL, str(link["href"])),
                        )
                    )
            vacancy = capacity - len(district_members)
            if vacancy < 0:
                raise RuntimeError(f"{district}: members {len(district_members)} exceeds capacity {capacity}")
            members.extend(district_members)
            district_checks.append(
                {
                    "district": district,
                    "capacity": capacity,
                    "members": len(district_members),
                    "vacancies": vacancy,
                    "source_url": SOURCE_URL,
                }
            )
        return members, district_checks

    def faction_after_link(self, link: Tag) -> str | None:
        text = ""
        for sibling in link.next_siblings:
            if isinstance(sibling, Tag) and sibling.name == "a" and "giin-giinprof" in str(sibling.get("href", "")):
                break
            if isinstance(sibling, NavigableString):
                text += str(sibling)
            elif isinstance(sibling, Tag):
                text += sibling.get_text(" ", strip=True)
            if "／" in text:
                break
        match = re.search(r"[（(]([^）)]+)[)）]", normalize_text(text))
        if not match:
            return None
        short = normalize_text(match.group(1))
        return FACTION_MAP.get(short, short)

    def correct_name(self, name: str) -> str:
        compact = name.replace(" ", "")
        return CORRECT_NAME_MAP.get(compact, name)

    def parse_profile(self, soup: BeautifulSoup) -> dict[str, object]:
        table = soup.find("table")
        if not isinstance(table, Tag):
            return {"elected_count": None, "committees": []}
        elected_count = None
        committees: list[str] = []
        for row in expand_table(table):
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in row]
            if len(values) < 3:
                continue
            label = values[-2]
            value = values[-1]
            if label == "期数":
                elected_count = parse_count(value)
            elif label in {"常任委員会", "特別委員会"}:
                if value and value not in committees:
                    committees.append(value)
        return {"elected_count": elected_count, "committees": committees}


def main() -> int:
    scraper = HiroshimaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
