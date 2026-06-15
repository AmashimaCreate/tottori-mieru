"""徳島県議会 議員一覧スクレイパー.

ソース: https://www.pref.tokushima.lg.jp/gikai/giin/senkyoku/
出力: docs/data/tokushima-pref/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import Tag

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

COUNCIL_ID = "tokushima-pref"
SOURCE_URL = "https://www.pref.tokushima.lg.jp/gikai/giin/senkyoku/"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_DISTRICTS = 13
EXPECTED_CAPACITY = 38
EXPECTED_VACANCIES = 2
EXPECTED_MEMBERS = 36

DISTRICT_RE = re.compile(r"^(.+?)\s*選挙区\s*[（(]\s*([0-9０-９]+)\s*人\s*[)）]$")
NAME_RE = re.compile(r"^(?P<name>.+?)[（(](?P<kana>.+?)[)）]$")


def article_node(soup) -> Tag:
    area = soup.find("div", class_="area3")
    if isinstance(area, Tag):
        return area
    content = soup.find("div", class_="article_body")
    if isinstance(content, Tag):
        return content
    h1 = soup.find("h1")
    return h1.parent if isinstance(h1, Tag) and isinstance(h1.parent, Tag) else soup


class TokushimaPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict[str, object]:
        soup = self.fetch(SOURCE_URL)
        article = article_node(soup)
        members: list[dict[str, object]] = []
        districts: list[dict[str, object]] = []
        current: dict[str, object] | None = None

        for node in article.find_all(["h3", "ul"]):
            if node.name == "h3":
                label = normalize_text(node.get_text(" ", strip=True))
                match = DISTRICT_RE.match(label)
                if not match:
                    continue
                current = {
                    "district": normalize_text(match.group(1)),
                    "listed_count": parse_count(match.group(2)) or 0,
                    "members": 0,
                    "vacancies": 0,
                }
                districts.append(current)
                continue

            if current is None or node.name != "ul":
                continue
            # Only the first-level member list below a district heading is parsed.
            for item in node.find_all("li", recursive=False):
                link = item.find("a", href=True, recursive=False)
                if not isinstance(link, Tag):
                    continue
                label = normalize_text(link.get_text(" ", strip=True))
                match = NAME_RE.match(label)
                if not match:
                    continue
                faction = None
                elected_count = None
                for sub in item.find_all("li"):
                    text = normalize_text(sub.get_text(" ", strip=True))
                    if text.startswith("所属会派"):
                        faction = normalize_text(text.split(":", 1)[-1] if ":" in text else text.split("：", 1)[-1])
                    elif text.startswith("当選回数"):
                        elected_count = parse_count(text)
                member = build_member(
                    council_id=COUNCIL_ID,
                    name=match.group("name"),
                    kana=match.group("kana"),
                    district=str(current["district"]),
                    faction=faction,
                    elected_count=elected_count,
                    profile_url=urljoin(SOURCE_URL, str(link["href"])),
                )
                members.append(member)
                current["members"] = int(current["members"]) + 1

        ensure_unique_ids(members)
        listed_total = sum(int(d["listed_count"]) for d in districts)
        if len(districts) != EXPECTED_DISTRICTS:
            raise RuntimeError(f"Expected {EXPECTED_DISTRICTS} districts, parsed {len(districts)}")
        if listed_total != EXPECTED_MEMBERS:
            raise RuntimeError(f"Listed total {listed_total} != {EXPECTED_MEMBERS}")
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}")
        for district in districts:
            if int(district["members"]) != int(district["listed_count"]):
                raise RuntimeError(
                    f"{district['district']}: members {district['members']} "
                    f"!= listed_count {district['listed_count']}"
                )

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": SOURCE_URL,
            "source_name": "徳島県議会 選挙区別 議員紹介",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "single_page_district_label_list",
                "district_count": len(districts),
                "capacity_total": EXPECTED_CAPACITY,
                "listed_total": listed_total,
                "vacancies": EXPECTED_VACANCIES,
                "expected_current_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "districts": districts,
                "notes": [
                    "公式名簿ページの選挙区見出し人数は合計36人。定数38との差2人を欠員として扱う",
                    "本文の選挙区見出しと直下の議員リストのみを解析",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        apply_member_contract(
            payload,
            teisu=EXPECTED_CAPACITY,
            source_basis_date="公式基準日記載なし",
            vacancy_details=[
                {
                    "label": "公式名簿掲載人数36人、定数38との差",
                    "ketsuin": EXPECTED_VACANCIES,
                    "source_url": SOURCE_URL,
                }
            ],
            anchor_type="official_roster_count_with_capacity_constant",
            notes=["定数38は調査済み定数アンカー。公式名簿上の選挙区見出し人数合計36人との差を欠員として扱う"],
        )
        return payload


def main() -> int:
    scraper = TokushimaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
