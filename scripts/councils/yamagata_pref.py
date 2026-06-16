"""山形県議会 議員一覧スクレイパー."""

from __future__ import annotations

import re
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
    expand_table,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "yamagata-pref"
SOURCE_URL = "https://www.pref.yamagata.jp/600006/kensei/assembly/giinsyokai/senkyokubetu/index.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 43


def parse_name_kana(value: str) -> tuple[str, str | None]:
    text = normalize_text(value)
    match = re.search(r"(.+?)[（(]\s*([^()（）]+)\s*[)）]", text)
    if not match:
        return text, None
    return normalize_text(match.group(1)), normalize_text(match.group(2))


class YamagataPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        refs, district_checks = self.parse_roster(soup)
        members: list[dict[str, object]] = []
        for ref in refs:
            profile = self.parse_profile(self.fetch(str(ref["profile_url"])))
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=str(profile.get("name") or ref["name"]),
                    kana=str(profile.get("kana") or ref.get("kana") or "") or None,
                    district=str(ref["district"]),
                    faction=str(profile.get("faction") or "") or None,
                    elected_count=None,
                    profile_url=str(ref["profile_url"]),
                    committees=list(profile.get("committees", [])),
                )
            )

        ensure_unique_ids(members)
        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")

        vacancy_details = [
            {"district": item["district"], "ketsuin": item["vacancies"], "source_url": SOURCE_URL}
            for item in district_checks
            if int(item["vacancies"]) > 0
        ]
        payload: dict[str, object] = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "山形県議会 選挙区別・五十音順",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_table_with_profile_allowlist",
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "parsed_members": len(members),
                "districts": district_checks,
                "notes": [
                    "選挙区別一覧から氏名・ふりがな・選挙区・定数を抽出",
                    "個別プロフィールは会派・委員会のみ許可リスト抽出",
                    "連絡先・その他本文は保存しない",
                    "当選回数は公式HTML上に見当たらないためnull",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date="議員任期: 令和5年4月30日～令和9年4月29日",
            vacancy_details=vacancy_details,
            anchor_source_url=SOURCE_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区別一覧の定数を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        table = soup.select_one("table.datatable")
        if not isinstance(table, Tag):
            raise RuntimeError("Yamagata roster table not found")
        refs: list[dict[str, object]] = []
        checks_by_district: dict[str, dict[str, object]] = {}
        for row in expand_table(table)[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in row]
            if len(values) < 4:
                continue
            district, capacity_text, name_text, kana = values[:4]
            capacity = parse_count(capacity_text)
            if not district or capacity is None:
                continue
            check = checks_by_district.setdefault(
                district,
                {
                    "district": district,
                    "capacity": capacity,
                    "members": 0,
                    "vacancies": 0,
                    "source_url": SOURCE_URL,
                },
            )
            link = row[2].find("a", href=True)
            if not isinstance(link, Tag) or name_text == "欠員":
                continue
            check["members"] = int(check["members"]) + 1
            refs.append(
                {
                    "district": district,
                    "capacity": capacity,
                    "name": name_text,
                    "kana": kana,
                    "profile_url": urljoin(SOURCE_URL, str(link["href"])),
                }
            )
        checks: list[dict[str, object]] = []
        for check in checks_by_district.values():
            vacancy = int(check["capacity"]) - int(check["members"])
            if vacancy < 0:
                raise RuntimeError(
                    f"{check['district']}: members {check['members']} exceeds capacity {check['capacity']}"
                )
            check["vacancies"] = vacancy
            checks.append(check)
        return refs, checks

    def parse_profile(self, soup: BeautifulSoup) -> dict[str, object]:
        data: dict[str, object] = {"committees": []}
        content = soup.select_one(".col2R") or soup
        headings = content.find_all("h3")
        for heading in headings:
            label = normalize_text(heading.get_text(" ", strip=True))
            values: list[str] = []
            for sibling in heading.next_siblings:
                if isinstance(sibling, Tag) and sibling.name == "h3":
                    break
                if isinstance(sibling, Tag) and sibling.name == "p":
                    text = normalize_text(sibling.get_text(" ", strip=True))
                    if text:
                        values.append(text)
            if label == "氏名" and values:
                name, kana = parse_name_kana(values[0])
                data["name"] = name
                data["kana"] = kana
            elif label == "所属会派" and values:
                data["faction"] = values[0]
            elif label == "所属委員会":
                data["committees"] = values
        return data


def main() -> int:
    scraper = YamagataPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
