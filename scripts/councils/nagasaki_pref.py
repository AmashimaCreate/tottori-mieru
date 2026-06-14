"""長崎県議会 議員一覧スクレイパー.

ソース: https://www.pref.nagasaki.jp/gikai/2010.html
出力: docs/data/nagasaki-pref/members.json
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.district_aggregate_profile import (  # noqa: E402
    DistrictAggregateConfig,
    DistrictAggregateProfileScraper,
)

COUNCIL_ID = "nagasaki-pref"
SOURCE_URL = "https://www.pref.nagasaki.jp/gikai/2010.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


class NagasakiPrefScraper(DistrictAggregateProfileScraper):
    def __init__(self) -> None:
        super().__init__(
            DistrictAggregateConfig(
                council_id=COUNCIL_ID,
                source_url=SOURCE_URL,
                output_path=OUT_PATH,
                min_count=40,
                parser="nagasaki",
            )
        )


def main() -> int:
    scraper = NagasakiPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
