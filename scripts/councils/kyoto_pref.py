"""京都府議会 議員一覧スクレイパー.

ソース: https://www.pref.kyoto.jp/gikai/shokai/50on.html
出力: docs/data/kyoto-pref/members.json
"""

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

COUNCIL_ID = "kyoto-pref"
SOURCE_URL = "https://www.pref.kyoto.jp/gikai/shokai/50on.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


def main() -> int:
    scraper = StaticMemberProfileScraper(
        StaticMemberProfileConfig(
            council_id=COUNCIL_ID,
            source_url=SOURCE_URL,
            output_path=OUT_PATH,
            min_count=55,
            profile_url_pattern=r"^/gikai/shokai/senkyoku/[^/]+/[^/]+\.html$",
            name_suffix_patterns=(),
            district_labels=("選挙区",),
            faction_labels=("所属会派", "会派"),
            elected_count_labels=("当選回数",),
            committee_labels=("所属委員会等", "所属委員会", "委員会"),
            teisu=60,
            source_basis_date="50音順名簿 更新日 2023-05-01",
            vacancy_details=(
                {
                    "label": "50音順名簿掲載59人、定数60との差",
                    "ketsuin": 1,
                    "source_url": SOURCE_URL,
                },
            ),
            anchor_type="official_roster_count_with_capacity_constant",
            anchor_notes=(
                "50音順名簿から個別プロフィールURLを抽出し、氏名・ふりがな・選挙区・会派・当選回数・委員会のみを許可リストで取得",
                "許可リスト外の個人向け項目は保存しない",
                "写真は取得せず、photo_urlは全員null",
            ),
        )
    )
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
