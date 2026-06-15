"""倉吉市議会 議員一覧スクレイパー.

ソース: https://www.city.kurayoshi.lg.jp/4253.htm
出力: docs/data/kurayoshi-city/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote, urljoin

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.councils.tottori_pref import make_slug, normalize_text  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "kurayoshi-city"
SOURCE_URL = "https://www.city.kurayoshi.lg.jp/4253.htm"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"


def clean_kana(text: str) -> str:
    return normalize_text(text).strip("()（）")


def parse_elected_count(text: str) -> int | None:
    m = re.search(r"(\d+)\s*回", text)
    return int(m.group(1)) if m else None


def index_after(lines: list[str], label: str) -> int | None:
    try:
        return lines.index(label) + 1
    except ValueError:
        return None


def append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def photo_map(soup) -> dict[int, str]:
    return {}


def split_member_blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    starts = [
        i
        for i, line in enumerate(lines)
        if re.match(r"^議席番号\d+", line)
    ]
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        blocks.append((lines[start], lines[start + 1 : end]))
    return blocks


def parse_affiliations(lines: list[str]) -> tuple[list[str], list[str]]:
    committees: list[str] = []
    positions: list[str] = []
    start = index_after(lines, "所属委員会")
    if start is None:
        return committees, positions

    for raw in lines[start:]:
        line = normalize_text(raw)
        if is_footer_or_contact_line(line):
            break
        role_match = re.search(r"（(委員長|副委員長)）", line)
        name = re.sub(r"（(委員長|副委員長)）", "", line).strip()
        if "委員会" in name:
            append_unique(committees, name)
            if role_match:
                append_unique(positions, f"{name}{role_match.group(1)}")
        else:
            append_unique(positions, name)
    return committees, positions


def is_footer_or_contact_line(line: str) -> bool:
    return bool(
        line
        and (
            line == "議会事務局"
            or line.startswith(
                (
                    "〒",
                    "電話番号:",
                    "ファックス:",
                    "FAX:",
                    "TEL:",
                    "場所:",
                    "添付資料",
                    "スマートフォン",
                    "ページの",
                    "先頭へ戻る",
                    "サイトマップ",
                    "プライバシーポリシー",
                    "このサイト",
                    "リンク・著作権",
                    "倉吉市役所",
                    "法人番号",
                    "窓口ご案内",
                    "開庁時間",
                    "市役所",
                    "庁舎案内",
                    "統計情報",
                    "Copyright",
                )
            )
        )
    )


def parse_block(header: str, lines: list[str], photos: dict[int, str]) -> dict | None:
    seat_match = re.match(r"^議席番号(\d+)(?:（(.+?)）)?$", header)
    if not seat_match:
        return None
    seat_no = int(seat_match.group(1))
    header_position = seat_match.group(2)

    name_idx = index_after(lines, "氏名")
    if name_idx is None or name_idx >= len(lines):
        return None
    name = normalize_text(lines[name_idx])
    name_kana = clean_kana(lines[name_idx + 1]) if name_idx + 1 < len(lines) else ""

    elected_count = None
    elected_idx = index_after(lines, "当選回数")
    if elected_idx is not None and elected_idx < len(lines):
        elected_count = parse_elected_count(lines[elected_idx])

    faction = ""
    faction_idx = index_after(lines, "会派")
    if faction_idx is not None and faction_idx < len(lines):
        faction = normalize_text(lines[faction_idx])

    committees, positions = parse_affiliations(lines)
    if header_position:
        positions.insert(0, header_position)

    slug = make_slug(name_kana)
    return {
        "id": f"{COUNCIL_ID}--{slug}",
        "council_id": COUNCIL_ID,
        "name": name,
        "name_kana": name_kana,
        "faction": faction,
        "elected_count": elected_count,
        "positions": positions,
        "committees": committees,
        "photo_url": photos.get(seat_no),
    }


def assign_unique_ids(members: list[dict]) -> None:
    counts: dict[str, int] = {}
    for member in members:
        base = member.get("id", "")
        n = counts.get(base, 0) + 1
        counts[base] = n
        if n > 1:
            member["id"] = f"{base}-{n}"


class KurayoshiScraper(CouncilScraperBase):
    def scrape_members(self) -> list[dict]:
        print(f"fetching {SOURCE_URL} ...")
        soup = self.fetch(SOURCE_URL)
        lines = [
            normalize_text(line)
            for line in soup.get_text("\n", strip=True).split("\n")
            if normalize_text(line)
        ]
        members = [
            member
            for header, block_lines in split_member_blocks(lines)
            if (member := parse_block(header, block_lines, photo_map(soup)))
            is not None
        ]
        assign_unique_ids(members)
        return members


def main() -> int:
    scraper = KurayoshiScraper()
    members = scraper.scrape_members()
    print(f"parsed {len(members)} members")
    scraper.assert_min_count(members, 15, "members")
    if not 15 <= len(members) <= 20:
        print(
            f"WARNING: expected 15-20 members, got {len(members)}",
            file=sys.stderr,
        )

    payload = {
        "council_id": COUNCIL_ID,
        "source_url": SOURCE_URL,
        "acquisition": "scraping",
        "members": members,
    }
    force_photo_null(payload)
    apply_member_contract(
        payload,
        teisu=17,
        source_basis_date="公式基準日記載なし",
        anchor_type="official_roster_count",
        notes=[
            "公式名簿一覧の掲載人数17人を月次更新の件数検算アンカーとして使用",
            "写真は取得せず、photo_urlは全員null",
        ],
    )
    scraper.save_json(OUT_PATH, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
