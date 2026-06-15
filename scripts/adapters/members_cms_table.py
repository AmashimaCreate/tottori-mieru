"""Reusable parser for CMS-style council member tables."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract  # noqa: E402


KATAKANA_TO_ROMAJI: dict[str, str] = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヲ": "wo", "ン": "n",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "ヴ": "vu",
}

COMPOUND_KATAKANA: dict[str, str] = {
    "キャ": "kya", "キュ": "kyu", "キョ": "kyo",
    "ギャ": "gya", "ギュ": "gyu", "ギョ": "gyo",
    "シャ": "sha", "シュ": "shu", "ショ": "sho",
    "ジャ": "ja", "ジュ": "ju", "ジョ": "jo",
    "チャ": "cha", "チュ": "chu", "チョ": "cho",
    "ニャ": "nya", "ニュ": "nyu", "ニョ": "nyo",
    "ヒャ": "hya", "ヒュ": "hyu", "ヒョ": "hyo",
    "ビャ": "bya", "ビュ": "byu", "ビョ": "byo",
    "ピャ": "pya", "ピュ": "pyu", "ピョ": "pyo",
    "ミャ": "mya", "ミュ": "myu", "ミョ": "myo",
    "リャ": "rya", "リュ": "ryu", "リョ": "ryo",
}


@dataclass(frozen=True)
class CmsMemberTableConfig:
    council_id: str
    source_url: str
    output_path: Path
    min_count: int
    name_column: str = "氏名"
    kana_column: str = "フリガナ"
    district_column: str = "選挙区"
    faction_column: str = "会派"
    elected_count_column: str = "期数"
    profile_committee_label: str = "所属委員会等"
    teisu: int | None = None
    source_basis_date: str | None = None
    vacancy_details: tuple[dict[str, Any], ...] = ()
    anchor_type: str = "official_roster_count"
    anchor_notes: tuple[str, ...] = ()


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    value = value.replace("\xa0", " ").replace("　", " ")
    value = re.sub(r"（注\d+）", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def make_slug(kana: str, fallback: str) -> str:
    source = normalize_text(kana) or normalize_text(fallback)
    source = source.translate(str.maketrans({
        "ァ": "ア", "ィ": "イ", "ゥ": "ウ", "ェ": "エ", "ォ": "オ",
        "ッ": "ツ", "ャ": "ヤ", "ュ": "ユ", "ョ": "ヨ",
    }))
    out: list[str] = []
    i = 0
    while i < len(source):
        ch = source[i]
        if ch in {" ", "-", "ー", "・"}:
            out.append("-")
            i += 1
            continue
        if i + 1 < len(source) and source[i : i + 2] in COMPOUND_KATAKANA:
            out.append(COMPOUND_KATAKANA[source[i : i + 2]])
            i += 2
            continue
        if ch in KATAKANA_TO_ROMAJI:
            out.append(KATAKANA_TO_ROMAJI[ch])
        elif re.match(r"[A-Za-z0-9]", ch):
            out.append(ch.lower())
        i += 1
    slug = re.sub(r"-+", "-", "".join(out)).strip("-")
    if slug:
        return slug
    return re.sub(r"[^a-z0-9]+", "-", fallback.lower()).strip("-") or "member"


def parse_int_like(value: str) -> int | None:
    normalized = normalize_text(value).translate(
        str.maketrans("０１２３４５６７８９", "0123456789")
    )
    match = re.search(r"\d+", normalized)
    return int(match.group(0)) if match else None


def row_cells(row: Tag) -> list[Tag]:
    return [cell for cell in row.find_all(["th", "td"], recursive=False)]


class CmsMemberTableScraper(CouncilScraperBase):
    """Scrape a member roster table plus allowlisted profile details."""

    def __init__(self, config: CmsMemberTableConfig) -> None:
        super().__init__()
        self.config = config

    def scrape_members(self) -> dict[str, Any]:
        soup = self.fetch(self.config.source_url)
        table = self.find_member_table(soup)
        members = self.parse_table(table)
        self.assert_min_count(members, self.config.min_count, "members")
        self.enrich_from_profiles(members)
        payload = {
            "council_id": self.config.council_id,
            "source_url": self.config.source_url,
            "acquisition": "scraping",
            "members": members,
        }
        if self.config.teisu is not None:
            apply_member_contract(
                payload,
                teisu=self.config.teisu,
                source_basis_date=self.config.source_basis_date,
                vacancy_details=list(self.config.vacancy_details),
                anchor_type=self.config.anchor_type,
                notes=list(self.config.anchor_notes),
            )
        return payload

    def find_member_table(self, soup: BeautifulSoup) -> Tag:
        for table in soup.find_all("table"):
            headers = [normalize_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
            if self.config.name_column in headers and self.config.faction_column in headers:
                return table
        raise RuntimeError("member table not found")

    def parse_table(self, table: Tag) -> list[dict[str, Any]]:
        rows = table.find_all("tr")
        if not rows:
            return []
        headers = [normalize_text(cell.get_text(" ", strip=True)) for cell in row_cells(rows[0])]
        index = {header: i for i, header in enumerate(headers)}
        members: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        for row in rows[1:]:
            cells = row_cells(row)
            if len(cells) < len(headers):
                continue
            name_cell = cells[index[self.config.name_column]]
            link = name_cell.find("a")
            name = normalize_text(link.get_text(" ", strip=True) if link else name_cell.get_text(" ", strip=True))
            if not name:
                continue
            kana = normalize_text(cells[index[self.config.kana_column]].get_text(" ", strip=True))
            slug = make_slug(kana, name)
            base_slug = slug
            counter = 2
            while slug in seen_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            seen_slugs.add(slug)
            profile_url = urljoin(self.config.source_url, link["href"]) if link and link.get("href") else None
            member = {
                "id": f"{self.config.council_id}--{slug}",
                "council_id": self.config.council_id,
                "name": name,
                "name_kana": kana,
                "district": normalize_text(cells[index[self.config.district_column]].get_text(" ", strip=True)),
                "faction": normalize_text(cells[index[self.config.faction_column]].get_text(" ", strip=True)) or None,
                "elected_count": parse_int_like(cells[index[self.config.elected_count_column]].get_text(" ", strip=True)),
                "positions": [],
                "committees": [],
                "photo_url": None,
                "official_profile_url": profile_url,
            }
            members.append(member)
        return members

    def enrich_from_profiles(self, members: list[dict[str, Any]]) -> None:
        for member in members:
            profile_url = member.get("official_profile_url")
            if not profile_url:
                continue
            soup = self.fetch(profile_url)
            self.parse_profile_allowed_fields(member, soup, profile_url)

    def parse_profile_allowed_fields(self, member: dict[str, Any], soup: BeautifulSoup, profile_url: str) -> None:
        body = soup.find("div", class_="detail_free") or soup

        table = body.find("table")
        if not table:
            return
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                continue
            label = normalize_text(cells[0].get_text(" ", strip=True))
            if label == self.config.profile_committee_label:
                items = [normalize_text(item) for item in cells[1].stripped_strings]
                member["committees"] = [item for item in items if item]
                member["positions"] = [
                    item
                    for item in member["committees"]
                    if "委員長" in item or "副委員長" in item
                ]
