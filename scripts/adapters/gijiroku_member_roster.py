"""Reusable parser for gijiroku.com g07 member roster pages."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    compact_name,
    ensure_unique_ids,
    normalize_text,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402


@dataclass(frozen=True)
class GijirokuRosterConfig:
    council_id: str
    base_url: str
    output_path: Path
    source_name: str
    teisu: int
    source_basis_date: str | None = None
    min_count: int = 1


def profile_key(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def add_unique(items: list[str], value: str | None) -> None:
    text = normalize_text(value)
    if text and text not in items:
        items.append(text)


class GijirokuMemberRosterScraper(CouncilScraperBase):
    """Scrape g07_*.asp member pages without storing contact fields."""

    def __init__(self, config: GijirokuRosterConfig) -> None:
        super().__init__()
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def fetch_cp932(self, url: str) -> BeautifulSoup:
        resp = self.session.get(url, timeout=self.request_timeout)
        resp.raise_for_status()
        time.sleep(self.sleep_seconds)
        text = resp.content.decode("cp932", errors="replace")
        return BeautifulSoup(text, "html.parser")

    def scrape_members(self) -> dict[str, Any]:
        roster_url = urljoin(self.config.base_url, "g07_giinlistP.asp")
        district_url = urljoin(self.config.base_url, "g07_giinlist_senkyoku.asp")
        committee_url = urljoin(self.config.base_url, "g07_Committee.asp")

        roster_soup = self.fetch_cp932(roster_url)
        district_soup = self.fetch_cp932(district_url)
        committee_soup = self.fetch_cp932(committee_url)

        members = self.parse_roster(roster_soup, roster_url)
        district_checks, district_profiles = self.parse_districts(district_soup, district_url)
        committees_by_profile = self.parse_committees(committee_soup)

        roster_profiles = {profile_key(str(member["official_profile_url"])) for member in members}
        missing_in_district = sorted(roster_profiles - district_profiles)
        missing_in_roster = sorted(district_profiles - roster_profiles)
        if missing_in_district or missing_in_roster:
            raise RuntimeError(
                f"gijiroku roster/district mismatch: "
                f"roster_only={missing_in_district}, district_only={missing_in_roster}"
            )

        for member in members:
            key = profile_key(str(member["official_profile_url"]))
            committee_data = committees_by_profile.get(key, {})
            member["committees"] = committee_data.get("committees", [])
            member["positions"] = committee_data.get("positions", [])

        self.assert_min_count(members, self.config.min_count, "members")
        ensure_unique_ids(members)

        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        if capacity_total != self.config.teisu:
            raise RuntimeError(f"capacity total {capacity_total} != {self.config.teisu}")
        if len(members) > capacity_total:
            raise RuntimeError(f"members {len(members)} exceeds capacity {capacity_total}")

        vacancy_details = [
            {
                "district": item["district"],
                "ketsuin": item["vacancies"],
                "source_url": item["source_url"],
            }
            for item in district_checks
            if int(item["vacancies"]) > 0
        ]
        payload: dict[str, Any] = {
            "council_id": self.config.council_id,
            "source_url": roster_url,
            "source_name": self.config.source_name,
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "gijiroku_g07_member_roster",
                "district_source_url": district_url,
                "committee_source_url": committee_url,
                "capacity_total": capacity_total,
                "district_count": len(district_checks),
                "parsed_members": len(members),
                "districts": district_checks,
                "roster_minus_district": missing_in_district,
                "district_minus_roster": missing_in_roster,
                "notes": [
                    "g07_giinlistP.aspから氏名・ふりがな・選挙区・会派のみを許可リスト抽出",
                    "許可リスト外の項目は保存しない",
                    "g07_giinlist_senkyoku.aspの区別定数を件数検算アンカーとして使用",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date=self.config.source_basis_date,
            vacancy_details=vacancy_details,
            anchor_source_url=district_url,
            anchor_type="official_gijiroku_district_capacity",
            notes=["gijiroku.com g07 系の選挙区別名簿を件数検算アンカーとして使用"],
        )
        return payload

    def parse_roster(self, soup: BeautifulSoup, roster_url: str) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cell in soup.select("td.tnowrap"):
            link = cell.find("a", href=re.compile(r"g07_giinlistS\.asp\?SrchID="))
            if not isinstance(link, Tag):
                continue
            text = cell.get_text("\n", strip=True)
            if "選挙区" not in text or "所属会派" not in text:
                continue
            url = urljoin(roster_url, str(link["href"]))
            key = profile_key(url)
            if key in seen:
                continue
            seen.add(key)

            name = normalize_text(link.get_text(" ", strip=True))
            kana_match = re.search(r"[（(]\s*([^()（）]+?)\s*[)）]", text)
            district_match = re.search(r"選挙区[：:]\s*([^\n\r]+)", text)
            faction_match = re.search(r"所属会派[：:]\s*([^\n\r]+)", text)
            members.append(
                build_member(
                    council_id=self.config.council_id,
                    name=name,
                    kana=kana_match.group(1) if kana_match else None,
                    district=district_match.group(1) if district_match else None,
                    faction=faction_match.group(1) if faction_match else None,
                    elected_count=None,
                    profile_url=url,
                )
            )
        return members

    def parse_districts(self, soup: BeautifulSoup, district_url: str) -> tuple[list[dict[str, Any]], set[str]]:
        checks: list[dict[str, Any]] = []
        profiles: set[str] = set()
        headings = soup.find_all("h2")
        for heading in headings:
            label = normalize_text(heading.get_text(" ", strip=True))
            if "選挙区" not in label or "定数" not in label:
                continue
            district = re.sub(r"\s*選挙区\s*定数.*$", "", label)
            capacity_match = re.search(r"定数[（(]\s*([0-9０-９]+)", label)
            capacity = parse_count(capacity_match.group(1) if capacity_match else "")
            if capacity is None:
                raise RuntimeError(f"capacity not found: {label}")
            district_profiles: set[str] = set()
            for sibling in heading.next_siblings:
                if isinstance(sibling, Tag) and sibling.name == "h2":
                    break
                if not isinstance(sibling, Tag):
                    continue
                for link in sibling.find_all("a", href=re.compile(r"g07_giinlistS\.asp\?SrchID=")):
                    key = profile_key(urljoin(district_url, str(link["href"])))
                    district_profiles.add(key)
                    profiles.add(key)
            current = len(district_profiles)
            vacancy = capacity - current
            if vacancy < 0:
                raise RuntimeError(f"{district}: members {current} exceeds capacity {capacity}")
            checks.append(
                {
                    "district": district,
                    "capacity": capacity,
                    "members": current,
                    "vacancies": vacancy,
                    "source_url": district_url,
                }
            )
        return checks, profiles

    def parse_committees(self, soup: BeautifulSoup) -> dict[str, dict[str, list[str]]]:
        output: dict[str, dict[str, list[str]]] = {}
        current_committee: str | None = None
        for tag in soup.find_all(["h3", "li"]):
            if tag.name == "h3":
                current_committee = normalize_text(tag.get_text(" ", strip=True))
                continue
            if tag.name != "li" or not current_committee:
                continue
            link = tag.find("a", href=re.compile(r"g07_giinlistS\.asp\?SrchID="))
            if not isinstance(link, Tag):
                continue
            key = profile_key(urljoin(self.config.base_url, str(link["href"])))
            item = output.setdefault(key, {"committees": [], "positions": []})
            add_unique(item["committees"], current_committee)
            role_match = re.search(r"[（(]\s*(委員長|副委員長)\s*[)）]", tag.get_text(" ", strip=True))
            if role_match:
                add_unique(item["positions"], f"{current_committee} {role_match.group(1)}")
        return output
