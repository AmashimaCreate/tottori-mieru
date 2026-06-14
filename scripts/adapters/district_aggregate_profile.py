"""Reusable parser for district-aggregate prefectural assembly rosters.

This adapter intentionally reads only allowlisted roster fields. Some source
pages include private/contact fields near each profile; those blocks are not
parsed except for committee/position labels where explicitly supported.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.members_cms_table import (  # noqa: E402
    make_slug,
    normalize_text,
    parse_int_like,
)
from scripts.base import CouncilScraperBase  # noqa: E402


@dataclass(frozen=True)
class DistrictAggregateConfig:
    council_id: str
    source_url: str
    output_path: Path
    min_count: int
    parser: str


KANJI_NUMERALS = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def compact_name(value: str | None) -> str:
    return normalize_text(value).replace(" ", "")


def parse_count(value: str) -> int | None:
    parsed = parse_int_like(value)
    if parsed is not None:
        return parsed
    text = normalize_text(value)
    if not text:
        return None
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = KANJI_NUMERALS.get(left, 1 if left == "" else 0)
        ones = KANJI_NUMERALS.get(right, 0) if right else 0
        return tens * 10 + ones
    return KANJI_NUMERALS.get(text)


def text_lines(tag: Tag) -> list[str]:
    return [
        normalize_text(line)
        for line in tag.get_text("\n", strip=True).splitlines()
        if normalize_text(line)
    ]


class DistrictAggregateProfileScraper(CouncilScraperBase):
    def __init__(self, config: DistrictAggregateConfig) -> None:
        super().__init__()
        self.config = config

    def scrape_members(self) -> dict[str, Any]:
        if self.config.parser == "nagasaki":
            members, checks = self.scrape_nagasaki()
        elif self.config.parser == "oita":
            members, checks = self.scrape_oita()
        else:
            raise ValueError(f"unknown parser: {self.config.parser}")

        self.assert_min_count(members, self.config.min_count, "members")
        self.ensure_unique_ids(members)
        return {
            "council_id": self.config.council_id,
            "source_url": self.config.source_url,
            "acquisition": "scraping",
            "checks": checks,
            "members": members,
        }

    def scrape_nagasaki(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        source_soup = self.fetch(self.config.source_url)
        first_district_url = self.first_nagasaki_district_url(source_soup)
        first_soup = self.fetch(first_district_url)
        nav_url = urljoin(self.config.source_url, "2010-16.html")
        nav_soup = self.fetch(nav_url)
        district_links = self.parse_nagasaki_district_links(nav_soup, nav_url)
        if not district_links:
            raise RuntimeError("Nagasaki district links not found")

        members: list[dict[str, Any]] = []
        district_checks: list[dict[str, Any]] = []
        for district in district_links:
            soup = first_soup if district["url"] == first_district_url else self.fetch(district["url"])
            parsed = self.parse_nagasaki_district_page(soup, district)
            if len(parsed) != district["capacity"]:
                raise RuntimeError(
                    f"{district['name']}: parsed {len(parsed)} members; "
                    f"expected {district['capacity']}"
                )
            members.extend(parsed)
            district_checks.append(
                {
                    "district": district["name"],
                    "capacity": district["capacity"],
                    "members": len(parsed),
                    "source_url": district["url"],
                }
            )

        expected_total = sum(district["capacity"] for district in district_links)
        if len(members) != expected_total:
            raise RuntimeError(
                f"Nagasaki total mismatch: parsed {len(members)}; expected {expected_total}"
            )

        return members, {
            "source_shape": "district_aggregate_profile",
            "district_count": len(district_links),
            "expected_members": expected_total,
            "parsed_members": len(members),
            "districts": district_checks,
            "notes": [
                "2010-16.html exists and is used as the official-looking navigation/template page for district links; it is not parsed as a member district.",
                "Only name, district, faction, elected_count, committees, and positions were parsed; contact fields were ignored.",
                "photo_url is intentionally null for all members.",
            ],
        }

    def first_nagasaki_district_url(self, soup: BeautifulSoup) -> str:
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if re.fullmatch(r"2010-\d{2}\.html(?:#[A-Za-z0-9_-]+)?", href):
                return urldefrag(urljoin(self.config.source_url, href))[0]
        raise RuntimeError("first Nagasaki district URL not found")

    def parse_nagasaki_district_links(self, soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=True):
            label = normalize_text(link.get_text(" ", strip=True))
            match = re.match(r"(.+?)\s*[（(]\s*([0-9０-９]+)\s*[)）]", label)
            if not match:
                continue
            href = urldefrag(urljoin(base_url, str(link["href"])))[0]
            if not re.search(r"/2010-\d{2}\.html$", href) or href in seen:
                continue
            seen.add(href)
            links.append(
                {
                    "name": normalize_text(match.group(1)),
                    "capacity": parse_count(match.group(2)) or 0,
                    "url": href,
                }
            )
        return links

    def parse_nagasaki_district_page(
        self, soup: BeautifulSoup, district: dict[str, Any]
    ) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        for block in soup.select("div.sub_detail2"):
            image_box = block.find("div", id="meibo01-1")
            if not image_box:
                continue
            image = image_box.find("img", alt=True)
            name = compact_name(image.get("alt") if image else "")
            if not name:
                continue
            anchor = image_box.find("a", id=True)
            anchor_id = normalize_text(anchor.get("id") if anchor else "")
            profile_url = district["url"] + (f"#{anchor_id}" if anchor_id else "")
            info_box = block.find("div", id="meibo01-2")
            info_lines = text_lines(info_box) if isinstance(info_box, Tag) else []
            elected_count = None
            faction = None
            for index, line in enumerate(info_lines):
                match = re.search(r"当選\s*([0-9０-９一二三四五六七八九十]+)\s*回", line)
                if not match:
                    continue
                elected_count = parse_count(match.group(1))
                if index + 1 < len(info_lines):
                    candidate = info_lines[index + 1]
                    if "議席番号" not in candidate:
                        faction = candidate
                break

            committees, positions = self.parse_nagasaki_committees(block)
            member = self.build_member(
                name=name,
                kana=None,
                district=district["name"],
                faction=faction,
                elected_count=elected_count,
                profile_url=profile_url,
                committees=committees,
                positions=positions,
            )
            members.append(member)
        return members

    def parse_nagasaki_committees(self, block: Tag) -> tuple[list[str], list[str]]:
        detail_box = block.find("div", id="meibo01-3")
        if not isinstance(detail_box, Tag):
            return [], []
        committees: list[str] = []
        positions: list[str] = []
        for line in text_lines(detail_box):
            if not (line.startswith("・") or line.startswith("※")):
                continue
            item = normalize_text(line.lstrip("・※").strip())
            if not item:
                continue
            if item in {"議長", "副議長"}:
                positions.append(item)
                continue
            committees.append(item)
            if "委員長" in item or "副委員長" in item:
                positions.append(item)
        return committees, positions

    def scrape_oita(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        soup = self.fetch(self.config.source_url)
        table = self.find_oita_member_table(soup)
        members: list[dict[str, Any]] = []
        district_checks: list[dict[str, Any]] = []
        current_district: dict[str, Any] | None = None
        seen_districts: set[str] = set()

        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 4:
                continue
            offset = 0
            first_cell = cells[0]
            if first_cell.has_attr("rowspan") or self.is_oita_district_label(first_cell):
                current_district = self.parse_oita_district_cell(first_cell)
                offset = 1
                if current_district["name"] not in seen_districts:
                    seen_districts.add(current_district["name"])
                    district_checks.append(
                        {
                            "district": current_district["name"],
                            "capacity": current_district["capacity"],
                            "members": 0,
                            "vacancies": 0,
                            "source_url": current_district["url"],
                        }
                    )
            if current_district is None:
                continue
            if len(cells) < offset + 4:
                continue
            name = compact_name(cells[offset].get_text(" ", strip=True))
            if not name or name == "―":
                district_checks[-1]["vacancies"] += 1
                continue
            kana = normalize_text(cells[offset + 1].get_text(" ", strip=True)) or None
            faction = normalize_text(cells[offset + 2].get_text(" ", strip=True)) or None
            elected_count = parse_count(cells[offset + 3].get_text(" ", strip=True))
            link = cells[offset].find("a", href=True)
            profile_url = urljoin(self.config.source_url, str(link["href"])) if link else current_district["url"]
            members.append(
                self.build_member(
                    name=name,
                    kana=kana,
                    district=current_district["name"],
                    faction=faction,
                    elected_count=elected_count,
                    profile_url=profile_url,
                    committees=[],
                    positions=[],
                )
            )
            district_checks[-1]["members"] += 1

        for district in district_checks:
            if district["members"] + district["vacancies"] != district["capacity"]:
                raise RuntimeError(
                    f"{district['district']}: members {district['members']} + vacancies "
                    f"{district['vacancies']} != capacity {district['capacity']}"
                )

        total_capacity = sum(d["capacity"] for d in district_checks)
        total_vacancies = sum(d["vacancies"] for d in district_checks)
        return members, {
            "source_shape": "district_aggregate_profile",
            "district_count": len(district_checks),
            "capacity_total": total_capacity,
            "vacancies": total_vacancies,
            "expected_current_members": total_capacity - total_vacancies,
            "parsed_members": len(members),
            "districts": district_checks,
            "notes": [
                "The official table has one vacancy marker (―); only sitting members are included.",
                "Only aggregate-table roster fields were parsed; contact-rich profile bodies were not parsed.",
                "photo_url is intentionally null for all members.",
            ],
        }

    def find_oita_member_table(self, soup: BeautifulSoup) -> Tag:
        for table in soup.find_all("table"):
            headers = [normalize_text(th.get_text(" ", strip=True)) for th in table.find_all("th")]
            if {"選挙区（定数）", "氏名", "ふりがな", "所属会派", "当選回数"}.issubset(headers):
                return table
        raise RuntimeError("Oita member table not found")

    def parse_oita_district_cell(self, cell: Tag) -> dict[str, Any]:
        label = normalize_text(cell.get_text(" ", strip=True))
        match = re.match(r"(.+?)\s*[（(]\s*([0-9０-９]+)\s*人?\s*[)）]", label)
        if not match:
            raise RuntimeError(f"Oita district label not parseable: {label}")
        link = cell.find("a", href=True)
        return {
            "name": normalize_text(match.group(1)),
            "capacity": parse_count(match.group(2)) or 0,
            "url": urljoin(self.config.source_url, str(link["href"])) if link else self.config.source_url,
        }

    def is_oita_district_label(self, cell: Tag) -> bool:
        label = normalize_text(cell.get_text(" ", strip=True))
        return bool(re.match(r".+?[（(]\s*[0-9０-９]+\s*人?\s*[)）]", label))

    def build_member(
        self,
        *,
        name: str,
        kana: str | None,
        district: str,
        faction: str | None,
        elected_count: int | None,
        profile_url: str,
        committees: list[str],
        positions: list[str],
    ) -> dict[str, Any]:
        slug = make_slug(kana or "", name)
        if slug == "member":
            digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
            slug = f"member-{digest}"
        return {
            "id": f"{self.config.council_id}--{slug}",
            "council_id": self.config.council_id,
            "name": name,
            "name_kana": kana,
            "district": district,
            "faction": faction,
            "elected_count": elected_count,
            "positions": positions,
            "committees": committees,
            "photo_url": None,
            "official_profile_url": profile_url,
        }

    def ensure_unique_ids(self, members: list[dict[str, Any]]) -> None:
        seen: dict[str, int] = {}
        for member in members:
            member_id = str(member["id"])
            seen[member_id] = seen.get(member_id, 0) + 1
            if seen[member_id] == 1:
                continue
            member["id"] = f"{member_id}-{seen[member_id]}"
