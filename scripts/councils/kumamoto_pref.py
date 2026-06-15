"""熊本県議会 議員一覧スクレイパー.

ソース: https://www.pref.kumamoto.jp/site/gikai/51858.html
出力: docs/data/kumamoto-pref/members.json
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.members_cms_table import (  # noqa: E402
    CmsMemberTableConfig,
    CmsMemberTableScraper,
)

COUNCIL_ID = "kumamoto-pref"
SOURCE_URL = "https://www.pref.kumamoto.jp/site/gikai/51858.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


class KumamotoPrefScraper(CmsMemberTableScraper):
    def __init__(self) -> None:
        super().__init__(
            CmsMemberTableConfig(
                council_id=COUNCIL_ID,
                source_url=SOURCE_URL,
                output_path=OUT_PATH,
                min_count=40,
                teisu=47,
                source_basis_date="公式基準日記載なし",
                anchor_type="official_roster_count",
                anchor_notes=(
                    "公式名簿一覧の掲載人数47人を月次更新の件数検算アンカーとして使用",
                    "写真は取得せず、photo_urlは全員null",
                ),
            )
        )


def main() -> int:
    scraper = KumamotoPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
