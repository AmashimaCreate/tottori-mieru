"茨城県議会 議員名簿スクレイパー."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.kanto_common import build_payload, clean, committee_list, member, out_path, text_list  # noqa: E402

COUNCIL_ID = "ibaraki-pref"
SOURCE_URL = "https://www.pref.ibaraki.jp/gikai/meibo/meibo_1.htm"
OUT_PATH = out_path(COUNCIL_ID)


class IbarakiPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> dict:
        soup = self.fetch(SOURCE_URL)
        members = []
        vacancies = []
        current_district = None
        for node in soup.select("h2, member-card"):
            if node.name == "h2":
                text = clean(node.get_text(" ", strip=True))
                current_district = text
                match = re.search(r"(.+?)選挙区[（(]欠員\s*([0-9０-９一二三四五六七八九十]+)[）)]", text)
                if match:
                    current_district = clean(match.group(1)) + "選挙区"
                    vacancies.append({"district": current_district, "ketsuin": parse_count(match.group(2)) or 1, "source_url": SOURCE_URL})
                continue
            if node.name != "member-card" or not isinstance(node, Tag):
                continue
            name = clean(str(node.get("img-alt", "")))
            attribution = node.find("member-attribution")
            attribution_lines = text_list(attribution) if isinstance(attribution, Tag) else []
            district = next((line for line in attribution_lines if "選挙区" in line), current_district)
            elected = next((parse_count(line) for line in attribution_lines if "当選" in line), None)
            faction = attribution_lines[1] if len(attribution_lines) >= 2 else None
            committees = []
            for tag in node.find_all(re.compile(r"^member-committee")):
                committees.extend(committee_list(tag.get_text(" ", strip=True)))
            members.append(
                member(
                    council_id=COUNCIL_ID,
                    name=name,
                    district=district,
                    faction=faction,
                    elected_count=elected,
                    profile_url=None,
                    committees=committees,
                )
            )
        if len(members) != 61:
            raise RuntimeError(f"Ibaraki parsed members {len(members)} != 61")
        return build_payload(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            source_name="茨城県議会 県議会議員名簿（一覧）",
            members=members,
            teisu=62,
            source_basis_date="令和8年6月8日現在 / 定数62人・現員61人",
            vacancy_details=vacancies,
            anchor_type="official_current_and_capacity_text",
            checks={
                "source_shape": "member_card_single_page",
                "declared_text": "令和8年6月8日現在 定数62人・現員61人",
            },
            notes=[
                "member-card要素から氏名・選挙区・会派・当選回数・委員会のみを取得",
                "写真は取得せず、photo_urlは全員null",
            ],
        )


def main() -> int:
    scraper = IbarakiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
