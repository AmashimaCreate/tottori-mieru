"""佐賀県議会 議員一覧スクレイパー.

ソース入口: https://www.pref.saga.lg.jp/gikai/list05019.html
出力: docs/data/saga-pref/members.json
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

from bs4 import Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.district_aggregate_profile import (  # noqa: E402
    compact_name,
    make_slug,
    parse_count,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "saga-pref"
ENTRY_URL = "https://www.pref.saga.lg.jp/gikai/list05019.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_DISTRICTS = 13
EXPECTED_MEMBERS = 37

DISTRICT_RE = re.compile(r"^(.+?)\s*定数\s*([0-9０-９]+)人$")
MEMBER_RE = re.compile(
    r"^(?P<name>.+?)\s*\((?P<faction>.+?)\)\s*\((?P<count>[0-9０-９]+)期\)"
)
REFERENCE_DATE_RE = re.compile(r"令和[0-9０-９]+年[0-9０-９]+月[0-9０-９]+日現在")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def kana_to_katakana(value: str) -> str:
    chars: list[str] = []
    for char in value:
        code = ord(char)
        if 0x3041 <= code <= 0x3096:
            chars.append(chr(code + 0x60))
        else:
            chars.append(char)
    return "".join(chars)


def tag_text_lines(tag: Tag) -> list[str]:
    return [
        normalize_text(line)
        for line in tag.get_text("\n", strip=True).splitlines()
        if normalize_text(line)
    ]


def parse_member_cell(cell: Tag) -> tuple[str, str | None, str, int] | None:
    lines = tag_text_lines(cell)
    if len(lines) < 2:
        return None

    joined = normalize_text(" ".join(lines[1:]))
    match = MEMBER_RE.search(joined)
    if not match:
        return None

    kana = lines[0]
    name = compact_name(match.group("name"))
    faction = re.sub(r"\s+", "", normalize_text(match.group("faction")))
    elected_count = parse_count(match.group("count"))
    if elected_count is None:
        return None
    return name, kana, faction, elected_count


class SagaPrefScraper(CouncilScraperBase):
    """Parse Saga's one-page WYSIWYG roster table."""

    def resolve_current_url(self) -> str:
        soup = self.fetch(ENTRY_URL)
        candidates: list[str] = []

        meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
        if isinstance(meta, Tag):
            content = str(meta.get("content", ""))
            match = re.search(r"url=([^;]+)", content, flags=re.I)
            if match:
                candidates.append(urljoin(ENTRY_URL, match.group(1).strip()))

        for script in soup.find_all("script"):
            text = script.get_text(" ", strip=True)
            for match in re.finditer(r"https://www\.pref\.saga\.lg\.jp/gikai/kiji\d+/index\.html", text):
                candidates.append(match.group(0))

        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if "/gikai/kiji" in href and "index.html" in href:
                candidates.append(urljoin(ENTRY_URL, href))

        unique = []
        for url in candidates:
            if url not in unique:
                unique.append(url)
        if not unique:
            raise RuntimeError(f"Could not resolve current roster URL from {ENTRY_URL}")
        return unique[0]

    def scrape_members(self) -> dict[str, object]:
        source_url = self.resolve_current_url()
        soup = self.fetch(source_url)
        article = soup.find("article") or soup

        full_text = article.get_text(" ", strip=True)
        reference_match = REFERENCE_DATE_RE.search(normalize_text(full_text))
        reference_date_label = reference_match.group(0) if reference_match else None
        updated = article.find("time")
        updated_label = updated.get_text(strip=True) if isinstance(updated, Tag) else None

        members: list[dict[str, object]] = []
        district_checks: list[dict[str, object]] = []
        current_district: dict[str, object] | None = None
        seen_ids: dict[str, int] = {}

        for node in article.find_all(["h2", "td", "th"]):
            lines = tag_text_lines(node)
            text = normalize_text(" ".join(lines))
            district_match = DISTRICT_RE.match(text)
            if district_match and node.name == "h2":
                if current_district is not None:
                    district_checks.append(current_district)
                current_district = {
                    "district": normalize_text(district_match.group(1)),
                    "capacity": int(normalize_text(district_match.group(2))),
                    "members": 0,
                }
                continue

            if node.name not in {"td", "th"} or current_district is None:
                continue

            parsed = parse_member_cell(node)
            if parsed is None:
                continue
            name, kana, faction, elected_count = parsed
            slug_seed = kana_to_katakana(kana) if kana else name
            slug = make_slug(slug_seed, name)
            seen_ids[slug] = seen_ids.get(slug, 0) + 1
            if seen_ids[slug] > 1:
                slug = f"{slug}-{seen_ids[slug]}"

            member = {
                "id": f"{COUNCIL_ID}--{slug}",
                "council_id": COUNCIL_ID,
                "name": name,
                "name_kana": kana,
                "faction": faction,
                "district": current_district["district"],
                "elected_count": elected_count,
                "positions": [],
                "committees": [],
                "photo_url": None,
                "official_profile_url": source_url,
            }
            members.append(member)
            current_district["members"] = int(current_district["members"]) + 1

        if current_district is not None:
            district_checks.append(current_district)

        alt_names = []
        for img in article.find_all("img", alt=True):
            alt = normalize_text(str(img.get("alt", "")))
            if alt.endswith("議員"):
                alt_names.append(compact_name(alt[:-2]))

        member_names = [str(member["name"]) for member in members]
        missing_from_alt = sorted(set(member_names) - set(alt_names))
        extra_alt = sorted(set(alt_names) - set(member_names))
        if missing_from_alt or extra_alt:
            raise RuntimeError(
                "Photo alt cross-check failed: "
                f"missing_from_alt={missing_from_alt}, extra_alt={extra_alt}"
            )

        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(
                f"Expected {EXPECTED_DISTRICTS} districts, parsed {len(district_checks)}"
            )
        if len(members) != EXPECTED_MEMBERS:
            raise RuntimeError(
                f"Expected {EXPECTED_MEMBERS} members, parsed {len(members)}"
            )
        capacity_total = sum(int(check["capacity"]) for check in district_checks)
        if capacity_total != len(members):
            raise RuntimeError(
                f"District capacity total {capacity_total} != parsed members {len(members)}"
            )

        payload = {
            "council_id": COUNCIL_ID,
            "source_url": source_url,
            "acquisition": "scraping",
            "schema_version": 1,
            "members": members,
            "checks": {
                "source_shape": "single_page_wysiwyg_table",
                "entry_url": ENTRY_URL,
                "resolved_url": source_url,
                "reference_date": reference_date_label,
                "updated_label": updated_label,
                "district_count": len(district_checks),
                "expected_members": EXPECTED_MEMBERS,
                "parsed_members": len(members),
                "photo_alt_members": len(alt_names),
                "districts": district_checks,
                "factions": sorted({str(member["faction"]) for member in members}),
                "notes": [
                    "写真はalt属性との照合にのみ使用し、photo_urlは保存しない",
                    "会派名がbrで分断されるセルは空白を除去して正規化",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date=reference_date_label or "公式基準日記載なし",
            anchor_source_url=source_url,
            anchor_type="official_district_capacity",
            notes=["選挙区別定数表を件数検算アンカーとして使用"],
        )
        return payload


def main() -> int:
    scraper = SagaPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
