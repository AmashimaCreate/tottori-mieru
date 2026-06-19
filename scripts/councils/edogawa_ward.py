"""edogawa-ward g07 council roster builder."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.gijiroku_member_roster import (  # noqa: E402
    GijirokuMemberRosterScraper,
    GijirokuRosterConfig,
)

COUNCIL_ID = "edogawa-ward"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


def main() -> int:
    scraper = GijirokuMemberRosterScraper(
        GijirokuRosterConfig(
            council_id=COUNCIL_ID,
            base_url="https://www.gikai.city.edogawa.tokyo.jp/",
            output_path=OUT_PATH,
            source_name="江戸川区議会 議員名簿",
            teisu=44,
            source_basis_date="公式名簿 掲載44人",
            min_count=35,
            single_district="江戸川区",
            district_path=None,
            committee_path=None,
            anchor_type="official_roster_count",
            notes=["公式ページ内に定数・欠員表示がないため、掲載現員44人を件数検算アンカーとして使用"],
        )
    )
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
