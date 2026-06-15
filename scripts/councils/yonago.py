"""米子市議会 議員一覧スクレイパー.

ソース: https://www.city.yonago.lg.jp/2919.htm
出力: docs/data/yonago-city/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import NavigableString, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "yonago-city"
SOURCE_URL = "https://www.city.yonago.lg.jp/2919.htm"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"

COMMITTEE_TYPES: dict[str, str] = {
    "総務政策": "常任",
    "民生教育": "常任",
    "都市経済": "常任",
    "予算決算": "常任",
    "議会運営": "議会運営",
    "基地問題等調査特別": "特別",
    "原子力発電・エネルギー問題等調査特別": "特別",
}
GLOBAL_POSITIONS = ("議長", "副議長")

HIRAGANA_TO_ROMAJI: dict[str, str] = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "を": "wo", "ん": "n",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "ji", "づ": "zu", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
}
COMPOUND_HIRAGANA: dict[str, str] = {
    "きゃ": "kya", "きゅ": "kyu", "きょ": "kyo",
    "ぎゃ": "gya", "ぎゅ": "gyu", "ぎょ": "gyo",
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho",
    "じゃ": "ja", "じゅ": "ju", "じょ": "jo",
    "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "にゃ": "nya", "にゅ": "nyu", "にょ": "nyo",
    "ひゃ": "hya", "ひゅ": "hyu", "ひょ": "hyo",
    "びゃ": "bya", "びゅ": "byu", "びょ": "byo",
    "ぴゃ": "pya", "ぴゅ": "pyu", "ぴょ": "pyo",
    "みゃ": "mya", "みゅ": "myu", "みょ": "myo",
    "りゃ": "rya", "りゅ": "ryu", "りょ": "ryo",
}


def make_slug(kana: str) -> str:
    if not kana:
        return ""
    s = kana.strip()
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in (" ", "　"):
            out.append("-")
            i += 1
            continue
        if i + 1 < len(s) and s[i : i + 2] in COMPOUND_HIRAGANA:
            out.append(COMPOUND_HIRAGANA[s[i : i + 2]])
            i += 2
            continue
        if ch in HIRAGANA_TO_ROMAJI:
            out.append(HIRAGANA_TO_ROMAJI[ch])
        i += 1
    return "".join(out).strip("-")


def normalize_text(s: str | None) -> str:
    if s is None:
        return ""
    s = s.replace(" ", " ").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


def strip_trailing_kana(s: str) -> str:
    return re.sub(r"\s+[ぁ-ゖー]+$", "", s).strip()


def absolute_url(src: str | None) -> str | None:
    if not src:
        return None
    if src.startswith("http"):
        return src
    if src.startswith("/"):
        return "https://www.city.yonago.lg.jp" + src
    return src


def cell_to_lines(td: Tag) -> list[str]:
    for br in td.find_all("br"):
        br.replace_with("\n")
    for p in td.find_all("p"):
        p.insert_before(NavigableString("\n"))
        p.insert_after(NavigableString("\n"))
    raw = td.get_text("")
    lines = [normalize_text(line) for line in raw.split("\n")]
    return [line for line in lines if line]


def match_committee(line: str) -> tuple[str, str] | None:
    for suffix, role in (("副委員長", "副委員長"), ("委員長", "委員長"), ("委員", "委員")):
        if line.endswith(suffix):
            name = normalize_text(line[: -len(suffix)])
            if name:
                return name, role
    return None


def append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def parse_member_cell(td: Tag, photo_url: str | None) -> dict | None:
    strong = td.find("strong")
    if not strong:
        return None
    name = normalize_text(strong.get_text())

    name_kana = ""
    ruby = strong.find_parent("ruby")
    if ruby:
        rt = ruby.find("rt")
        if rt:
            name_kana = normalize_text(rt.get_text())

    faction = ""
    elected_count: int | None = None
    positions: list[str] = []
    committees: list[str] = []

    for line in cell_to_lines(td):
        if name and name in line and (not name_kana or name_kana in line):
            continue
        if name and line.startswith(name):
            continue

        m = re.search(r"当選回数[：:]\s*(\d+)\s*回", line)
        if m:
            elected_count = int(m.group(1))
            continue

        m = re.match(r"^会派[：:]\s*(.+?)\s*$", line)
        if m:
            faction = strip_trailing_kana(normalize_text(m.group(1)))
            continue

        if line == "無所属":
            faction = "無所属"
            continue

        m = re.match(r"^呼称[：:]\s*(.+?)\s*$", line)
        if m:
            faction = strip_trailing_kana(normalize_text(m.group(1)))
            continue

        if line in GLOBAL_POSITIONS:
            append_unique(positions, line)
            continue

        committee = match_committee(line)
        if committee:
            committee_name, role = committee
            append_unique(committees, committee_name)
            if role in ("委員長", "副委員長"):
                append_unique(positions, f"{committee_name}{role}")

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
        "photo_url": photo_url,
    }


def assign_unique_ids(members: list[dict]) -> None:
    counts: dict[str, int] = {}
    for member in members:
        base = member.get("id", "")
        if not base:
            continue
        n = counts.get(base, 0) + 1
        counts[base] = n
        if n > 1:
            member["id"] = f"{base}-{n}"


class YonagoScraper(CouncilScraperBase):
    def scrape_members(self) -> list[dict]:
        print(f"fetching {SOURCE_URL} ...")
        soup = self.fetch(SOURCE_URL)
        table = soup.find("table", attrs={"summary": "議員名簿"})
        if not table:
            raise RuntimeError("議員名簿テーブルが見つかりません")

        members: list[dict] = []
        for tr in table.find_all("tr"):
            if tr.find("td", attrs={"colspan": "2"}):
                continue
            tds = tr.find_all("td", recursive=False)
            i = 0
            while i < len(tds):
                td = tds[i]
                img = td.find("img")
                if (
                    img
                    and img.get("src", "").endswith("spacer.gif")
                    and td.get("rowspan")
                ):
                    i += 1
                    continue
                if img and i + 1 < len(tds) and tds[i + 1].find("strong"):
                    member = parse_member_cell(tds[i + 1], None)
                    if member:
                        members.append(member)
                    i += 2
                else:
                    i += 1

        assign_unique_ids(members)
        return members


def main() -> int:
    scraper = YonagoScraper()
    members = scraper.scrape_members()
    print(f"parsed {len(members)} members")
    scraper.assert_min_count(members, 10, "members")
    if len(members) != 26:
        print(f"WARNING: expected 26 members, got {len(members)}", file=sys.stderr)

    payload = {
        "council_id": COUNCIL_ID,
        "source_url": SOURCE_URL,
        "acquisition": "scraping",
        "members": members,
    }
    force_photo_null(payload)
    apply_member_contract(
        payload,
        teisu=26,
        source_basis_date="公式基準日記載なし",
        anchor_type="official_roster_count",
        notes=[
            "公式名簿一覧の掲載人数26人を月次更新の件数検算アンカーとして使用",
            "写真は取得せず、photo_urlは全員null",
        ],
    )
    scraper.save_json(OUT_PATH, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
