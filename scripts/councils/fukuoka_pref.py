"""福岡県議会 議員一覧スクレイパー."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.static_member_profile import (  # noqa: E402
    StaticMemberProfileConfig,
    StaticMemberProfileScraper,
)

COUNCIL_ID = "fukuoka-pref"
SOURCE_URL = "https://www.gikai.pref.fukuoka.lg.jp/site/giin/all.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


class FukuokaPrefScraper(StaticMemberProfileScraper):
    def __init__(self) -> None:
        super().__init__(
            StaticMemberProfileConfig(
                council_id=COUNCIL_ID,
                source_url=SOURCE_URL,
                output_path=OUT_PATH,
                min_count=80,
                profile_url_pattern=r"^/site/giin/[^/]+\.html$",
                exclude_url_patterns=(
                    r"/site/giin/(?:all|index|gijouzu|name-kanji)\.html$",
                ),
                content_selector=".detail_free",
            )
        )


def main() -> int:
    scraper = FukuokaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
