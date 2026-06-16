"""岩手県議会 議員一覧スクレイパー."""

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

COUNCIL_ID = "iwate-pref"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


def main() -> int:
    scraper = GijirokuMemberRosterScraper(
        GijirokuRosterConfig(
            council_id=COUNCIL_ID,
            base_url="https://iwatekengikai.gijiroku.com/",
            output_path=OUT_PATH,
            source_name="岩手県議会 議員名簿（五十音順）",
            teisu=48,
            source_basis_date="公式基準日記載なし",
            min_count=40,
        )
    )
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
