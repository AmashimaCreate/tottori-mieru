"""香川県議会 議員一覧スクレイパー.

ソース: https://www.pref.kagawa.lg.jp/gikai/meibo/50onjun_ketu1.html
出力: docs/data/kagawa-pref/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    ensure_unique_ids,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract  # noqa: E402

COUNCIL_ID = "kagawa-pref"
SOURCE_URL = "https://www.pref.kagawa.lg.jp/gikai/meibo/50onjun_ketu1.html"
DISTRICT_URL = "https://www.pref.kagawa.lg.jp/gikai/meibo/4_5.html"
CAPACITY_URL = "https://www.pref.kagawa.lg.jp/gikai/meibo/4_1.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_DISTRICTS = 13
EXPECTED_CAPACITY = 41
EXPECTED_VACANCIES = 1
EXPECTED_MEMBERS = 40

DISTRICT_RE = re.compile(
    r"^(.+?)選挙区[（(]\s*([0-9０-９]+)\s*名\s*[)）]"
    r"(?:[（(]\s*欠員\s*([0-9０-９]+)\s*名\s*[)）])?"
)
FILENAME_ALT_RE = re.compile(r"^name[0-9]+[_-][0-9]+(?:_[0-9]+)?$")

FACTION_MAP = {
    "自由民主党議員会": "香川県議会自由民主党議員会",
    "国民民主党議員会": "香川県議会国民民主党議員会",
    "国民民主党": "香川県議会国民民主党議員会",
    "立憲民主党議員会": "香川県議会立憲民主党議員会",
    "立憲民主党": "香川県議会立憲民主党議員会",
    "公明党議員会": "香川県議会公明党議員会",
    "日本共産党議員団": "日本共産党香川県議会議員団",
    "日本共産党": "日本共産党香川県議会議員団",
}


def profile_key(url: str) -> str:
    return urlparse(url).path


def faction_label(value: str | None) -> str | None:
    key = normalize_text(value).replace(" ", "")
    if not key:
        return None
    return FACTION_MAP.get(key, key)


def clean_committee(value: str | None) -> tuple[str | None, str | None]:
    text = normalize_text(value)
    if not text:
        return None, None
    position = None
    if text.startswith("◎"):
        position = "委員長"
    elif text.startswith("〇") or text.startswith("○"):
        position = "副委員長"
    text = normalize_text(text.lstrip("◎〇○"))
    return text or None, position


def member_name_from_cell(cell: Tag) -> str:
    for image in reversed(cell.find_all("img", alt=True)):
        alt = normalize_text(str(image.get("alt", "")))
        if alt:
            return alt
    return normalize_text(cell.get_text(" ", strip=True))


class KagawaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        main_soup = self.fetch(SOURCE_URL)
        district_soup = self.fetch(DISTRICT_URL)
        capacity_soup = self.fetch(CAPACITY_URL)

        capacities = self.parse_capacity_table(capacity_soup)
        district_map, district_checks = self.parse_district_page(district_soup)
        rows = self.parse_gojuon_table(main_soup)

        missing_names = [key for key, row in rows.items() if FILENAME_ALT_RE.fullmatch(row["name"])]
        for key in missing_names:
            rows[key]["name"] = self.fetch_profile_name(urljoin(SOURCE_URL, rows[key]["profile_path"]))

        missing_districts = sorted(set(rows) - set(district_map))
        extra_districts = sorted(set(district_map) - set(rows))
        if missing_districts or extra_districts:
            raise RuntimeError(
                "Kagawa profile URL join mismatch: "
                f"missing_districts={missing_districts}, extra_districts={extra_districts}"
            )

        members: list[dict[str, object]] = []
        for key, row in rows.items():
            district = district_map[key]["district"]
            if district in capacities and int(capacities[district]) != int(district_map[key]["capacity"]):
                raise RuntimeError(
                    f"Kagawa capacity mismatch for {district}: "
                    f"{capacities[district]} != {district_map[key]['capacity']}"
                )
            committees: list[str] = []
            positions: list[str] = []
            for committee_text in row["committee_values"]:
                committee, role = clean_committee(committee_text)
                if not committee:
                    continue
                committees.append(committee)
                if role:
                    positions.append(f"{committee} {role}")
            members.append(
                build_member(
                    council_id=COUNCIL_ID,
                    name=str(row["name"]),
                    kana=None,
                    district=district,
                    faction=row["faction"] if isinstance(row["faction"], str) else None,
                    elected_count=int(row["elected_count"]) if row["elected_count"] is not None else None,
                    profile_url=urljoin(SOURCE_URL, str(row["profile_path"])),
                    committees=committees,
                    positions=positions,
                )
            )

        ensure_unique_ids(members)
        capacity_total = sum(int(v) for v in capacities.values())
        vacancies = sum(int(d["vacancies"]) for d in district_checks)
        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"Expected {EXPECTED_DISTRICTS} districts, parsed {len(district_checks)}")
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"Capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if vacancies != EXPECTED_VACANCIES:
            raise RuntimeError(f"Vacancies {vacancies} != {EXPECTED_VACANCIES}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        for district in district_checks:
            if int(district["members"]) + int(district["vacancies"]) != int(district["capacity"]):
                raise RuntimeError(
                    f"{district['district']}: members {district['members']} + vacancies "
                    f"{district['vacancies']} != capacity {district['capacity']}"
                )

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "香川県議会 議員紹介（五十音順）",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_gojuon_table_with_district_join",
                "district_url": DISTRICT_URL,
                "capacity_url": CAPACITY_URL,
                "district_count": len(district_checks),
                "capacity_total": capacity_total,
                "vacancies": vacancies,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "gojuon_rows": len(rows),
                "profile_name_fallbacks": missing_names,
                "districts": district_checks,
                "factions": sorted({str(member["faction"]) for member in members}),
                "notes": [
                    "五十音順ページの氏名・会派・当選回数と、選挙区別ページの選挙区をプロフィールURLで結合",
                    "丸亀市選挙区は公式ページに欠員1名と明記されているため現員40名",
                    "写真は取得せず、氏名画像altは氏名抽出にのみ使用",
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
            source_basis_date="公式基準日記載なし",
            vacancy_details=vacancy_details,
            anchor_source_url=CAPACITY_URL,
            anchor_type="official_district_capacity",
            notes=["選挙区別定数表と選挙区別名簿を件数検算アンカーとして使用"],
        )
        return payload

    def parse_gojuon_table(self, soup: BeautifulSoup) -> dict[str, dict[str, object]]:
        table = soup.find("table", class_="datatable")
        if not isinstance(table, Tag):
            raise RuntimeError("Kagawa gojuon table not found")
        rows: dict[str, dict[str, object]] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 6:
                continue
            link = cells[0].find("a", href=True)
            if not isinstance(link, Tag):
                continue
            profile_path = str(link["href"])
            name = member_name_from_cell(cells[0])
            faction = faction_label(cells[1].get_text(" ", strip=True))
            rows[profile_key(urljoin(SOURCE_URL, profile_path))] = {
                "name": name,
                "profile_path": profile_path,
                "faction": faction,
                "elected_count": parse_count(cells[2].get_text(" ", strip=True)),
                "committee_values": [
                    normalize_text(cells[3].get_text(" ", strip=True)),
                    normalize_text(cells[4].get_text(" ", strip=True)),
                ],
            }
        return rows

    def parse_district_page(self, soup: BeautifulSoup) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
        current: dict[str, object] | None = None
        checks: list[dict[str, object]] = []
        mapping: dict[str, dict[str, object]] = {}
        for node in soup.find_all(["h2", "table"]):
            if node.name == "h2":
                label = normalize_text(node.get_text(" ", strip=True))
                match = DISTRICT_RE.match(label)
                if not match:
                    continue
                current = {
                    "district": normalize_text(match.group(1)),
                    "capacity": parse_count(match.group(2)) or 0,
                    "members": 0,
                    "vacancies": parse_count(match.group(3)) or 0,
                    "source_url": DISTRICT_URL,
                }
                checks.append(current)
                continue
            if current is None or node.name != "table":
                continue
            for tr in node.find_all("tr"):
                cells = tr.find_all("td", recursive=False)
                if len(cells) < 2:
                    continue
                link = cells[1].find("a", href=True)
                if not isinstance(link, Tag):
                    continue
                key = profile_key(urljoin(DISTRICT_URL, str(link["href"])))
                mapping[key] = {
                    "district": current["district"],
                    "capacity": current["capacity"],
                    "faction": faction_label(cells[0].get_text(" ", strip=True)),
                }
                current["members"] = int(current["members"]) + 1
        return mapping, checks

    def parse_capacity_table(self, soup: BeautifulSoup) -> dict[str, int]:
        table = soup.find("table", class_="datatable")
        if not isinstance(table, Tag):
            raise RuntimeError("Kagawa capacity table not found")
        capacities: dict[str, int] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 3:
                continue
            district = normalize_text(cells[0].get_text(" ", strip=True))
            if district == "13選挙区":
                continue
            count = parse_count(cells[2].get_text(" ", strip=True))
            if district and count is not None:
                capacities[district] = count
        return capacities

    def fetch_profile_name(self, profile_url: str) -> str:
        soup = self.fetch(profile_url)
        h1 = soup.find("h1")
        if isinstance(h1, Tag):
            return normalize_text(h1.get_text(" ", strip=True))
        title = soup.find("title")
        if isinstance(title, Tag):
            return normalize_text(title.get_text(" ", strip=True).split("｜", 1)[0])
        raise RuntimeError(f"Kagawa profile name not found: {profile_url}")


def main() -> int:
    scraper = KagawaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
