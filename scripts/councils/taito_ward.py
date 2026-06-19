"""taito-ward g07 council roster builder."""

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

COUNCIL_ID = "taito-ward"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


def main() -> int:
    scraper = GijirokuMemberRosterScraper(
        GijirokuRosterConfig(
            council_id=COUNCIL_ID,
            base_url="https://taito.gijiroku.com/voices/",
            output_path=OUT_PATH,
            source_name="台東区議会 議員名簿",
            teisu=32,
            source_basis_date="公式名簿 掲載31人・欠員1人",
            min_count=25,
            single_district="台東区",
            district_path=None,
            committee_path=None,
            vacancy_details=[
                {
                    "district": "台東区",
                    "ketsuin": 1,
                    "source_url": "https://taito.gijiroku.com/voices/g07_giinlistP.asp",
                }
            ],
            anchor_type="official_roster_count_with_vacancy",
            notes=["公式名簿に空席行があるため、欠員1人として記録"],
        )
    )
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
