"""鳥取市議会 議員一覧スクレイパー.

ソース: https://www.city.tottori.lg.jp/site/shigikai/6355.html
出力: docs/data/tottori-city/members.json
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
from scripts.councils.tottori_pref import (  # noqa: E402
    append_unique,
    make_slug,
    name_key,
    normalize_text,
)
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "tottori-city"
SOURCE_URL = "https://www.city.tottori.lg.jp/site/shigikai/6355.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
CHAIRS_URL = "https://www.city.tottori.lg.jp/site/shigikai/6372.html"
COMMITTEE_INDEX_URL = "https://www.city.tottori.lg.jp/site/shigikai/6336.html"


def split_name_kana(text: str) -> tuple[str, str]:
    m = re.match(r"^(.+?)[（(](.+?)[）)]$", normalize_text(text))
    if not m:
        return normalize_text(text), ""
    return normalize_text(m.group(1)), normalize_text(m.group(2))


def parse_elected_count(text: str) -> int | None:
    m = re.search(r"(\d+)\s*回", text)
    return int(m.group(1)) if m else None


def cell_lines(cell: Tag) -> list[str]:
    lines = [
        normalize_text(line)
        for line in cell.get_text("\n", strip=True).split("\n")
    ]
    return [line for line in lines if line]


def photo_url(cell: Tag) -> str | None:
    return None


def parse_row(tr: Tag) -> dict | None:
    cells = tr.find_all(["td", "th"])
    if len(cells) < 7 or cells[0].name == "th":
        return None

    name, name_kana = split_name_kana(cells[2].get_text(" ", strip=True))
    if not name:
        return None

    committees = cell_lines(cells[5])
    slug = make_slug(name_kana)
    return {
        "id": f"{COUNCIL_ID}--{slug}",
        "council_id": COUNCIL_ID,
        "name": name,
        "name_kana": name_kana,
        "faction": normalize_text(cells[6].get_text(" ", strip=True)),
        "elected_count": parse_elected_count(cells[4].get_text(" ", strip=True)),
        "positions": [],
        "committees": committees,
        "photo_url": photo_url(cells[1]),
        "official_profile_url": None,
    }


def assign_unique_ids(members: list[dict]) -> None:
    counts: dict[str, int] = {}
    for member in members:
        base = member.get("id", "")
        n = counts.get(base, 0) + 1
        counts[base] = n
        if n > 1:
            member["id"] = f"{base}-{n}"


def chair_roles_from_page(soup) -> dict[str, str]:
    roles: dict[str, str] = {}
    body = soup.find(id="main_body") or soup
    for paragraph in body.find_all("p"):
        label = normalize_text(paragraph.get_text(" ", strip=True))
        if not re.search(r"第[0-9０-９]+代", label) or "議長" not in label:
            continue

        role = "副議長" if "副議長" in label else "議長"
        name_node = paragraph.find_next("strong")
        if not name_node:
            continue
        person = normalize_text(name_node.get_text(" ", strip=True))
        if person:
            roles[name_key(person)] = role
    return roles


def committee_links_from_index(soup) -> list[str]:
    body = soup.find(id="main_body") or soup
    links: list[str] = []
    seen: set[str] = set()
    for link in body.find_all("a", href=True):
        text = normalize_text(link.get_text(" ", strip=True))
        href = link.get("href", "")
        if "委員会" not in text or not re.search(r"/page/\d+\.html$", href):
            continue
        url = urljoin(COMMITTEE_INDEX_URL, href)
        if url in seen:
            continue
        seen.add(url)
        links.append(url)
    return links


def normalize_committee_name(text: str) -> str:
    title = normalize_text(text)
    title = re.sub(r"^議員名簿\s*", "", title)
    title = re.sub(r"[（(]\d+名[）)]", "", title)
    return normalize_text(title)


def committee_name_from_page(soup) -> str:
    body = soup.find(id="main_body") or soup
    for tag in body.find_all(["h2", "h1"]):
        title = normalize_committee_name(tag.get_text(" ", strip=True))
        if "委員会" in title:
            return title
    return ""


def person_after_role(lines: list[str], index: int, role: str) -> str:
    rest = normalize_text(lines[index][len(role) :])
    if rest:
        return rest
    if index + 1 < len(lines):
        return normalize_text(lines[index + 1])
    return ""


def committee_positions_from_detail(soup) -> dict[str, list[str]]:
    committee_name = committee_name_from_page(soup)
    if not committee_name:
        return {}

    positions: dict[str, list[str]] = {}
    body = soup.find(id="main_body") or soup
    for cell in body.find_all(["td", "th"]):
        lines = cell_lines(cell)
        for index, line in enumerate(lines):
            role = ""
            if line.startswith("副委員長"):
                role = "副委員長"
            elif line.startswith("委員長"):
                role = "委員長"
            if not role:
                continue

            person = person_after_role(lines, index, role)
            if not person:
                continue
            append_unique(
                positions.setdefault(name_key(person), []),
                f"{committee_name} {role}",
            )
    return positions


class TottoriCityScraper(CouncilScraperBase):
    def scrape_members(self) -> list[dict]:
        print(f"fetching {SOURCE_URL} ...")
        soup = self.fetch(SOURCE_URL)
        table = soup.find("table")
        if not table:
            raise RuntimeError("議員名簿テーブルが見つかりません")

        members = [
            member
            for tr in table.find_all("tr")
            if (member := parse_row(tr)) is not None
        ]
        assign_unique_ids(members)
        self.enrich_positions(members)
        return members

    def enrich_positions(self, members: list[dict]) -> None:
        by_name = {name_key(member["name"]): member for member in members}

        print(f"fetching {CHAIRS_URL} ...")
        chair_soup = self.fetch(CHAIRS_URL)
        for key, role in chair_roles_from_page(chair_soup).items():
            member = by_name.get(key)
            if not member:
                print(f"WARNING: could not match {role} name: {key}", file=sys.stderr)
                continue
            append_unique(member["positions"], role)

        print(f"fetching {COMMITTEE_INDEX_URL} ...")
        index_soup = self.fetch(COMMITTEE_INDEX_URL)
        committee_links = committee_links_from_index(index_soup)
        if not committee_links:
            print("WARNING: committee detail links were not found", file=sys.stderr)

        for url in committee_links:
            print(f"fetching {url} ...")
            detail_soup = self.fetch(url)
            committee_positions = committee_positions_from_detail(detail_soup)
            for key, positions in committee_positions.items():
                member = by_name.get(key)
                if not member:
                    print(
                        f"WARNING: could not match committee role name: {key}",
                        file=sys.stderr,
                    )
                    continue
                for position in positions:
                    append_unique(member["positions"], position)


def main() -> int:
    scraper = TottoriCityScraper()
    members = scraper.scrape_members()
    print(f"parsed {len(members)} members")
    scraper.assert_min_count(members, 25, "members")
    if not 25 <= len(members) <= 40:
        print(
            f"WARNING: expected 25-40 members, got {len(members)}",
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
        teisu=32,
        source_basis_date="公式基準日記載なし",
        anchor_type="official_roster_count",
        notes=[
            "公式名簿一覧の掲載人数32人を月次更新の件数検算アンカーとして使用",
            "写真は取得せず、photo_urlは全員null",
        ],
    )
    scraper.save_json(OUT_PATH, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
