"""Reusable parser for gsl-service.net member CSV roster pages."""

from __future__ import annotations

import csv
import io
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
class GslCsvRosterConfig:
    council_id: str
    source_url: str
    output_path: Path
    source_name: str
    teisu: int
    source_basis_date: str | None = None
    min_count: int = 1


def profile_key(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.rstrip("/") + "/"


def decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


class GslServiceCsvRosterScraper(CouncilScraperBase):
    """Scrape gsl-service member CSV while ignoring contact columns."""

    def __init__(self, config: GslCsvRosterConfig) -> None:
        super().__init__()
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def fetch_html(self, url: str) -> BeautifulSoup:
        resp = self.session.get(url, timeout=self.request_timeout)
        resp.raise_for_status()
        time.sleep(self.sleep_seconds)
        if not resp.encoding or resp.encoding.lower() in {"iso-8859-1", "latin-1"}:
            resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "html.parser")

    def fetch_bytes(self, url: str) -> bytes:
        resp = self.session.get(url, timeout=self.request_timeout)
        resp.raise_for_status()
        time.sleep(self.sleep_seconds)
        return resp.content

    def scrape_members(self) -> dict[str, Any]:
        soup = self.fetch_html(self.config.source_url)
        csv_url = self.find_csv_url(soup)
        profile_urls = self.profile_urls_by_name(soup)
        district_checks, district_profiles = self.parse_districts(soup)
        rows = self.parse_csv(csv_url)

        members: list[dict[str, Any]] = []
        csv_profiles: set[str] = set()
        for row in rows:
            name = normalize_text(row["氏名"])
            profile_url = profile_urls.get(compact_name(name))
            if profile_url:
                csv_profiles.add(profile_key(profile_url))
            members.append(
                build_member(
                    council_id=self.config.council_id,
                    name=name,
                    kana=row.get("ふりがな"),
                    district=row.get("選挙区"),
                    faction=row.get("所属会派"),
                    elected_count=parse_count(row.get("当選回数")),
                    profile_url=profile_url,
                    committees=[
                        item
                        for item in re.split(r"[、,，/／]+", normalize_text(row.get("所属委員会")))
                        if normalize_text(item)
                    ],
                )
            )

        missing_profiles = sorted(csv_profiles - district_profiles)
        extra_district_profiles = sorted(district_profiles - csv_profiles)
        if missing_profiles or extra_district_profiles:
            raise RuntimeError(
                f"gsl csv/district mismatch: csv_only={missing_profiles}, "
                f"district_only={extra_district_profiles}"
            )

        self.assert_min_count(members, self.config.min_count, "members")
        ensure_unique_ids(members)
        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        if capacity_total != self.config.teisu:
            raise RuntimeError(f"capacity total {capacity_total} != {self.config.teisu}")

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
            "source_url": self.config.source_url,
            "source_name": self.config.source_name,
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "gsl_service_member_csv",
                "csv_source_url": csv_url,
                "capacity_total": capacity_total,
                "district_count": len(district_checks),
                "parsed_members": len(members),
                "districts": district_checks,
                "notes": [
                    "CSVから氏名・ふりがな・選挙区・当選回数・会派・委員会のみを許可リスト抽出",
                    "許可リスト外の項目は保存しない",
                    "選挙区別HTMLの定数を件数検算アンカーとして使用",
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
            anchor_source_url=self.config.source_url,
            anchor_type="official_gsl_district_capacity",
            notes=["gsl-service.net のCSVと選挙区別HTMLを突合"],
        )
        return payload

    def find_csv_url(self, soup: BeautifulSoup) -> str:
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if href.lower().endswith(".csv") and "giin_ichiran" in href:
                return urljoin(self.config.source_url, href)
        raise RuntimeError("member CSV link not found")

    def parse_csv(self, csv_url: str) -> list[dict[str, str]]:
        text = decode_csv_bytes(self.fetch_bytes(csv_url))
        rows = list(csv.reader(io.StringIO(text)))
        header_index = next(
            index for index, row in enumerate(rows) if any(normalize_text(cell) == "氏名" for cell in row)
        )
        headers = [normalize_text(cell) for cell in rows[header_index]]
        output: list[dict[str, str]] = []
        for raw in rows[header_index + 1 :]:
            if not any(normalize_text(cell) for cell in raw):
                continue
            record = {
                headers[index]: normalize_text(raw[index]) if index < len(raw) else ""
                for index in range(len(headers))
                if headers[index]
            }
            if record.get("氏名"):
                output.append(record)
        return output

    def profile_urls_by_name(self, soup: BeautifulSoup) -> dict[str, str]:
        urls: dict[str, str] = {}
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if "/profile/" not in href:
                continue
            name = compact_name(link.get_text(" ", strip=True))
            if not name:
                continue
            urls.setdefault(name, urljoin(self.config.source_url, href))
        return urls

    def parse_districts(self, soup: BeautifulSoup) -> tuple[list[dict[str, Any]], set[str]]:
        checks: list[dict[str, Any]] = []
        profiles: set[str] = set()
        in_section = False
        for heading in soup.find_all(["h2", "h4"]):
            text = normalize_text(heading.get_text(" ", strip=True))
            if heading.name == "h2":
                if "選挙区別一覧" in text:
                    in_section = True
                    continue
                if in_section:
                    break
            if not in_section or heading.name != "h4":
                continue
            match = re.match(r"(.+?)\s*[（(]\s*([0-9０-９]+)\s*人?\s*[)）]", text)
            if not match:
                continue
            district = normalize_text(match.group(1))
            capacity = parse_count(match.group(2)) or 0
            district_profiles: set[str] = set()
            for sibling in heading.next_siblings:
                if isinstance(sibling, Tag) and sibling.name in {"h2", "h4"}:
                    break
                if not isinstance(sibling, Tag):
                    continue
                for link in sibling.find_all("a", href=True):
                    if "/profile/" not in str(link["href"]):
                        continue
                    key = profile_key(urljoin(self.config.source_url, str(link["href"])))
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
                    "source_url": self.config.source_url,
                }
            )
        return checks, profiles
