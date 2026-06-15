"""鳥取県議会 議員一覧スクレイパー.

ソース: https://www.pref.tottori.lg.jp/75928.htm
出力: docs/data/tottori-pref/members.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "tottori-pref"
SOURCE_URL = "https://www.pref.tottori.lg.jp/75928.htm"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
CHAIR_URL = "https://www.pref.tottori.lg.jp/75926.htm"
VICE_CHAIR_URL = "https://www.pref.tottori.lg.jp/75927.htm"
COMMITTEE_ROSTER_URL = "https://www.pref.tottori.lg.jp/322790.htm"

FACTIONS = {"自由民主党", "民主とっとり", "公明党", "無所属"}

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


def normalize_text(s: str | None) -> str:
    if s is None:
        return ""
    s = s.replace(" ", " ").replace("　", " ")
    return re.sub(r"\s+", " ", s).strip()


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


def split_name_kana(text: str) -> tuple[str, str]:
    m = re.match(r"^(.+?)（(.+?)）$", normalize_text(text))
    if not m:
        return normalize_text(text), ""
    return normalize_text(m.group(1)), normalize_text(m.group(2))


def append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def name_key(name: str) -> str:
    return re.sub(r"\s+", "", normalize_text(name))


def parse_int_like(text: str) -> int | None:
    normalized = normalize_text(text).translate(
        str.maketrans("０１２３４５６７８９", "0123456789")
    )
    m = re.search(r"\d+", normalized)
    return int(m.group(0)) if m else None


def normalize_committee_title(text: str) -> str:
    title = normalize_text(text)
    title = re.sub(r"[（(]\d+名[）)]", "", title)
    return normalize_text(title)


def parse_member(title: Tag, status: Tag | None) -> dict:
    link = title.find("a")
    name, name_kana = split_name_kana(link.get_text(" ", strip=True) if link else "")
    profile_url = urljoin(SOURCE_URL, link["href"]) if link and link.get("href") else None
    faction = ""
    committees: list[str] = []

    if status:
        for a in status.find_all("a"):
            category = normalize_text(a.get_text(" ", strip=True))
            if category.endswith("選挙区"):
                continue
            if category in FACTIONS:
                faction = category
                continue
            if "委員会" in category:
                append_unique(committees, category)

    slug = make_slug(name_kana)
    return {
        "id": f"{COUNCIL_ID}--{slug}",
        "council_id": COUNCIL_ID,
        "name": name,
        "name_kana": name_kana,
        "faction": faction,
        "elected_count": None,
        "positions": [],
        "committees": committees,
        "photo_url": None,
        "official_profile_url": profile_url,
    }


def parse_profile_allowed_fields(soup, profile_url: str) -> tuple[int | None, str | None]:
    """Return only allowlisted fields from a member profile page."""
    elected_count: int | None = None
    photo_url: str | None = None

    contents = soup.find("div", class_="Contents")
    if not contents:
        return elected_count, photo_url

    table = contents.find("table")
    if not table:
        return elected_count, photo_url

    for row in table.find_all("tr"):
        header = row.find("th")
        cells = row.find_all("td")
        label_cell = header or (cells[-2] if len(cells) >= 2 else None)
        if not label_cell:
            continue
        label = normalize_text(label_cell.get_text(" ", strip=True))
        if label != "期数":
            continue
        if cells:
            elected_count = parse_int_like(cells[-1].get_text(" ", strip=True))
        break

    return elected_count, photo_url


def chair_name_from_page(soup, role: str) -> str | None:
    text = normalize_text(soup.get_text(" ", strip=True))
    match = re.search(rf"第[0-9０-９]+代鳥取県議会{role}\s+(\S+)\s+(\S+)", text)
    if not match:
        return None
    return normalize_text(f"{match.group(1)} {match.group(2)}")


def committee_positions_from_page(soup) -> dict[str, list[str]]:
    positions: dict[str, list[str]] = {}
    for title in soup.find_all("h2", class_="Title"):
        committee_name = normalize_committee_title(title.get_text(" ", strip=True))
        if not committee_name or "委員会" not in committee_name:
            continue

        contents = title.find_parent("div", class_="h2frame")
        if contents:
            contents = contents.find_next_sibling("div", class_="Contents")
        if not contents:
            contents = title.find_next("div", class_="Contents")
        table = contents.find("table") if contents else None
        if not table:
            continue

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            role = normalize_text(cells[0].get_text(" ", strip=True))
            person = normalize_text(cells[1].get_text(" ", strip=True))
            if not person:
                continue
            if role.startswith("副委員長"):
                append_unique(
                    positions.setdefault(name_key(person), []),
                    f"{committee_name} 副委員長",
                )
            elif role.startswith("委員長"):
                append_unique(
                    positions.setdefault(name_key(person), []),
                    f"{committee_name} 委員長",
                )
    return positions


def assign_unique_ids(members: list[dict]) -> None:
    counts: dict[str, int] = {}
    for member in members:
        base = member.get("id", "")
        n = counts.get(base, 0) + 1
        counts[base] = n
        if n > 1:
            member["id"] = f"{base}-{n}"


class TottoriPrefScraper(CouncilScraperBase):
    def scrape_members(self) -> list[dict]:
        print(f"fetching {SOURCE_URL} ...")
        soup = self.fetch(SOURCE_URL)
        blog = soup.find(id="moduleid155189")
        if not blog:
            raise RuntimeError("議員名簿ブログ領域が見つかりません")

        members: list[dict] = []
        for title in soup.find_all("h2", class_="Title"):
            status = title.find_next_sibling("p", class_="Status")
            member = parse_member(title, status)
            if member["name"]:
                members.append(member)

        assign_unique_ids(members)
        self.enrich_member_profiles(members)
        self.enrich_positions(members)
        return members

    def enrich_member_profiles(self, members: list[dict]) -> None:
        for member in members:
            profile_url = member.get("official_profile_url")
            if not profile_url:
                continue
            print(f"fetching profile {member['name']} ...")
            soup = self.fetch(profile_url)
            elected_count, photo = parse_profile_allowed_fields(soup, profile_url)
            if elected_count is not None:
                member["elected_count"] = elected_count

    def enrich_positions(self, members: list[dict]) -> None:
        by_name = {name_key(member["name"]): member for member in members}

        print(f"fetching {CHAIR_URL} ...")
        chair_soup = self.fetch(CHAIR_URL)
        chair_name = chair_name_from_page(chair_soup, "議長")
        if chair_name and name_key(chair_name) in by_name:
            append_unique(by_name[name_key(chair_name)]["positions"], "議長")
        else:
            print(f"WARNING: could not match chair name: {chair_name}", file=sys.stderr)

        print(f"fetching {VICE_CHAIR_URL} ...")
        vice_soup = self.fetch(VICE_CHAIR_URL)
        vice_name = chair_name_from_page(vice_soup, "副議長")
        if vice_name and name_key(vice_name) in by_name:
            append_unique(by_name[name_key(vice_name)]["positions"], "副議長")
        else:
            print(f"WARNING: could not match vice chair name: {vice_name}", file=sys.stderr)

        print(f"fetching {COMMITTEE_ROSTER_URL} ...")
        committee_soup = self.fetch(COMMITTEE_ROSTER_URL)
        committee_positions = committee_positions_from_page(committee_soup)
        for key, positions in committee_positions.items():
            member = by_name.get(key)
            if not member:
                print(f"WARNING: could not match committee role name: {key}", file=sys.stderr)
                continue
            for position in positions:
                append_unique(member["positions"], position)


def main() -> int:
    scraper = TottoriPrefScraper()
    members = scraper.scrape_members()
    print(f"parsed {len(members)} members")
    scraper.assert_min_count(members, 30, "members")
    if not 30 <= len(members) <= 40:
        print(
            f"WARNING: expected 30-40 members, got {len(members)}",
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
        teisu=35,
        source_basis_date="公式基準日記載なし",
        anchor_type="official_roster_count",
        notes=[
            "公式名簿一覧の掲載人数35人を月次更新の件数検算アンカーとして使用",
            "個別プロフィールから期数のみ取得し、写真は取得しない",
        ],
    )
    scraper.save_json(OUT_PATH, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
