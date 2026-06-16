"""宮城県議会 議員一覧スクレイパー."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.static_member_profile import table_label_values  # noqa: E402
from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    ensure_unique_ids,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "miyagi-pref"
SOURCE_URL = "https://www.pref.miyagi.jp/site/kengikai/18meibo-kubetu.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 59
EXPECTED_DISTRICTS = 23


def parse_name_kana(value: str) -> tuple[str, str | None]:
    text = normalize_text(value)
    match = re.search(r"(.+?)[（(]\s*([^()（）]+)\s*[)）]", text)
    if not match:
        return text, None
    return normalize_text(match.group(1)), normalize_text(match.group(2))


class MiyagiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        roster_refs, district_checks = self.parse_district_roster(soup)
        members: list[dict[str, object]] = []
        for ref in roster_refs:
            profile = self.parse_profile(self.fetch(str(ref["profile_url"])))
            name = str(profile.get("name") or ref["name"])
            kana = profile.get("kana")
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=name,
                    kana=str(kana) if kana else None,
                    district=str(profile.get("district") or ref["district"]),
                    faction=str(profile.get("faction") or "") or None,
                    elected_count=profile.get("elected_count"),
                    profile_url=str(ref["profile_url"]),
                )
            )

        ensure_unique_ids(members)
        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"District count {len(district_checks)} != {EXPECTED_DISTRICTS}")

        vacancy_details = [
            {"district": item["district"], "ketsuin": item["vacancies"], "source_url": SOURCE_URL}
            for item in district_checks
            if int(item["vacancies"]) > 0
        ]
        payload: dict[str, object] = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "宮城県議会 議員名簿（選挙区別）",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_district_heading_with_profile_allowlist",
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "parsed_members": len(members),
                "districts": district_checks,
                "notes": [
                    "選挙区別ページから選挙区・定数・プロフィールURLを抽出",
                    "個別プロフィールは氏名・ふりがな・会派・選挙区・当選回数のみ許可リスト抽出",
                    "許可リスト外の項目は保存しない",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            vacancy_details=vacancy_details,
            anchor_source_url=SOURCE_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区見出しの定数を件数検算アンカーとして使用"],
        )
        return payload

    def parse_district_roster(self, soup: BeautifulSoup) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        refs: list[dict[str, object]] = []
        checks: list[dict[str, object]] = []
        for heading in soup.find_all("h3"):
            label = normalize_text(heading.get_text(" ", strip=True))
            match = re.match(r"(.+?)[（(]\s*定数[:：]\s*([0-9０-９]+)\s*名", label)
            if not match:
                continue
            district = normalize_text(match.group(1))
            capacity = parse_count(match.group(2)) or 0
            paragraph = heading.find_next_sibling("p")
            district_refs: list[dict[str, object]] = []
            if isinstance(paragraph, Tag):
                for link in paragraph.find_all("a", href=True):
                    item = {
                        "name": normalize_text(link.get_text(" ", strip=True)),
                        "district": district,
                        "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                    }
                    refs.append(item)
                    district_refs.append(item)
            vacancy = capacity - len(district_refs)
            if vacancy < 0:
                raise RuntimeError(f"{district}: members {len(district_refs)} exceeds capacity {capacity}")
            checks.append(
                {
                    "district": district,
                    "capacity": capacity,
                    "members": len(district_refs),
                    "vacancies": vacancy,
                    "source_url": SOURCE_URL,
                }
            )
        return refs, checks

    def parse_profile(self, soup: BeautifulSoup) -> dict[str, object]:
        values = table_label_values(soup)
        name, kana = parse_name_kana(values.get("氏名", ""))
        return {
            "name": name,
            "kana": kana,
            "district": values.get("選挙区"),
            "faction": values.get("所属会派"),
            "elected_count": parse_count(values.get("当選回数")),
        }


def main() -> int:
    scraper = MiyagiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
