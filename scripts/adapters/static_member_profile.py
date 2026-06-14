"""Reusable parser for static member lists with individual profile pages."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.members_cms_table import make_slug, parse_int_like  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402


PROFILE_INFO_RE = re.compile(r"(.+?)[（(]\s*([^（）()]+?)\s*[）)]")
HIRAGANA_TO_KATAKANA = str.maketrans(
    {chr(code): chr(code + 0x60) for code in range(ord("ぁ"), ord("ゖ") + 1)}
)


@dataclass(frozen=True)
class StaticMemberProfileConfig:
    council_id: str
    source_url: str
    output_path: Path
    min_count: int
    profile_url_pattern: str
    exclude_url_patterns: tuple[str, ...] = ()
    content_selector: str | None = None
    name_suffix_patterns: tuple[str, ...] = (r"議員のプロフィール$",)
    district_labels: tuple[str, ...] = ("選挙区",)
    faction_labels: tuple[str, ...] = ("会派", "所属会派")
    elected_count_labels: tuple[str, ...] = ("当選回数",)
    committee_labels: tuple[str, ...] = ("所属委員会等", "所属委員会", "委員会")
    name_labels: tuple[str, ...] = ("氏名",)
    kana_labels: tuple[str, ...] = ("ふりがな",)
    profile_link_requires_image: bool = False
    list_position_patterns: dict[str, str] = field(
        default_factory=lambda: {
            "議長": "議長",
            "副議長": "副議長",
        }
    )


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    value = value.replace("\xa0", " ").replace("\u200b", "")
    value = value.replace("　", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def kana_to_slug_source(value: str) -> str:
    return normalize_text(value).translate(HIRAGANA_TO_KATAKANA)


def parse_name_and_kana(value: str) -> tuple[str, str | None]:
    text = normalize_text(value)
    match = PROFILE_INFO_RE.search(text)
    if match:
        name = normalize_text(match.group(1))
        kana = normalize_text(match.group(2))
        return name, kana or None
    return text, None


def split_items(value: str) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    rough = re.split(r"[、,，\n]+", text)
    items: list[str] = []
    for item in rough:
        item = normalize_text(item)
        if not item:
            continue
        # Some official pages separate committee names only by spaces.
        parts = re.split(r"\s+(?=[^\s]+委員会|[^\s]+特別)", item)
        items.extend(normalize_text(part) for part in parts if normalize_text(part))
    return items


def clean_name(raw: str, suffix_patterns: tuple[str, ...]) -> tuple[str, str | None]:
    text = normalize_text(raw)
    for pattern in suffix_patterns:
        text = re.sub(pattern, "", text).strip()
    name, kana = parse_name_and_kana(text)
    return normalize_text(name), kana


def table_label_values(soup: BeautifulSoup | Tag) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        label = normalize_text(cells[0].get_text(" ", strip=True))
        value = normalize_text(cells[1].get_text(" ", strip=True))
        if label and value and label not in values:
            values[label] = value
    return values


def first_label_value(values: dict[str, str], labels: tuple[str, ...]) -> str | None:
    for label in labels:
        if label in values:
            return values[label]
    return None


def url_path(url: str) -> str:
    return urlparse(url).path


class StaticMemberProfileScraper(CouncilScraperBase):
    """Scrape a static roster page and allowlisted fields from profiles.

    The profile pages often contain contact details. This adapter only reads
    labels explicitly named in StaticMemberProfileConfig.
    """

    def __init__(self, config: StaticMemberProfileConfig) -> None:
        super().__init__()
        self.config = config
        self.profile_re = re.compile(config.profile_url_pattern)
        self.exclude_res = [re.compile(pattern) for pattern in config.exclude_url_patterns]

    def scrape_members(self) -> dict[str, Any]:
        soup = self.fetch(self.config.source_url)
        profile_refs = self.profile_refs(soup)
        members: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()
        for ref in profile_refs:
            soup = self.fetch(ref["url"])
            member = self.parse_profile(ref, soup)
            slug = make_slug(kana_to_slug_source(member.get("name_kana") or ""), member["name"])
            base_slug = slug
            counter = 2
            while slug in seen_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            seen_slugs.add(slug)
            member["id"] = f"{self.config.council_id}--{slug}"
            members.append(member)

        self.assert_min_count(members, self.config.min_count, "members")
        return {
            "council_id": self.config.council_id,
            "source_url": self.config.source_url,
            "acquisition": "scraping",
            "members": members,
        }

    def profile_refs(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=True):
            if self.config.profile_link_requires_image and link.find("img") is None:
                continue
            url = urljoin(self.config.source_url, link["href"])
            path = url_path(url)
            if not self.profile_re.search(path):
                continue
            if any(pattern.search(path) for pattern in self.exclude_res):
                continue
            if url in seen:
                continue
            seen.add(url)
            text = normalize_text(link.get_text(" ", strip=True))
            positions = [
                position
                for pattern, position in self.config.list_position_patterns.items()
                if pattern in text
            ]
            refs.append({"url": url, "text": text, "positions": positions})
        return refs

    def parse_profile(self, ref: dict[str, Any], soup: BeautifulSoup) -> dict[str, Any]:
        content: BeautifulSoup | Tag = soup
        if self.config.content_selector:
            selected = soup.select_one(self.config.content_selector)
            if selected:
                content = selected

        values = table_label_values(content)
        h1 = soup.find("h1")
        heading = h1.get_text(" ", strip=True) if h1 else ref.get("text", "")

        name, kana = clean_name(heading, self.config.name_suffix_patterns)
        table_name = first_label_value(values, self.config.name_labels)
        if table_name:
            table_parsed_name, table_kana = parse_name_and_kana(table_name)
            name = table_parsed_name or name
            kana = table_kana or kana
        table_kana = first_label_value(values, self.config.kana_labels)
        if table_kana:
            kana = table_kana

        committees = split_items(first_label_value(values, self.config.committee_labels) or "")
        positions = list(dict.fromkeys([*ref.get("positions", []), *[
            item for item in committees if "委員長" in item or "副委員長" in item
        ]]))

        return {
            "id": "",
            "council_id": self.config.council_id,
            "name": name,
            "name_kana": kana,
            "district": first_label_value(values, self.config.district_labels),
            "faction": first_label_value(values, self.config.faction_labels),
            "elected_count": parse_int_like(
                first_label_value(values, self.config.elected_count_labels) or ""
            ),
            "positions": positions,
            "committees": committees,
            "photo_url": None,
            "official_profile_url": ref["url"],
        }
