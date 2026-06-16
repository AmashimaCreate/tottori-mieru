"""秋田県議会 議員一覧スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.gsl_service_member_csv import (  # noqa: E402
    GslCsvRosterConfig,
    GslServiceCsvRosterScraper,
)

COUNCIL_ID = "akita-pref"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


def main() -> int:
    scraper = GslServiceCsvRosterScraper(
        GslCsvRosterConfig(
            council_id=COUNCIL_ID,
            source_url="https://pref.akita.gsl-service.net/doc/2018042300017/",
            output_path=OUT_PATH,
            source_name="秋田県議会 議員紹介",
            teisu=41,
            source_basis_date="議員一覧CSV: 令和7年5月26日版",
            min_count=40,
        )
    )
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
