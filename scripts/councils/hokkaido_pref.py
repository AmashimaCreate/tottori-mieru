"""北海道議会 議員名簿PDFパーサ.

ソース入口: https://www.gikai.pref.hokkaido.lg.jp/meibo/index.html
出力: docs/data/hokkaido-pref/members.json
"""

from __future__ import annotations

import io
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pdfplumber
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.members_cms_table import make_slug  # noqa: E402
from scripts.adapters.single_page_roster import parse_count  # noqa: E402
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

COUNCIL_ID = "hokkaido-pref"
ENTRY_URL = "https://www.gikai.pref.hokkaido.lg.jp/meibo/index.html"
PDF_INDEX_URL = "https://www.gikai.pref.hokkaido.lg.jp/meibo/pdf-index.html"
COMMITTEE_INDEX_URL = "https://www.gikai.pref.hokkaido.lg.jp/iinkai/index2.html"
OUT_PATH = REPO_ROOT / "docs" / "data" / COUNCIL_ID / "members.json"
EXPECTED_CAPACITY = 100
EXPECTED_DISTRICTS = 46
SOURCE_BASIS_DATE = "2026-05-25"

FACTIONS = [
    "自民党・道民会議",
    "民主・道民連合",
    "北海道結志会",
    "公明党",
    "日本共産党",
    "北海道維新の会",
]

NAME_LINE_RE = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<kana>[^()]+)\)$")
GRID_MEMBER_RE = re.compile(r"(?P<name>.+?)\s*(?P<count>[0-9]+)(?=\s|$)")
COMMITTEE_NAME_RE = re.compile(r"(?P<name>[^()※]+?)\s*\([^()]+\)")
CURRENT_EXCLUDE_WORDS = ("辞職", "逝去")
HIRAGANA_TO_KATAKANA = str.maketrans(
    {chr(code): chr(code + 0x60) for code in range(ord("ぁ"), ord("ゖ") + 1)}
)


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", value).strip()


def compact_name(value: str | None) -> str:
    return normalize_text(value).replace(" ", "")


def kana_to_katakana(value: str | None) -> str:
    return normalize_text(value).translate(HIRAGANA_TO_KATAKANA)


def normalize_committee_name(value: str | None) -> str:
    return compact_name(value).replace("･", "・")


def add_unique(items: list[str], value: str | None) -> None:
    text = normalize_text(value)
    if text and text not in items:
        items.append(text)


class HokkaidoPrefScraper(CouncilScraperBase):
    """Parse Hokkaido's PDF-only roster with two-source count checks."""

    def scrape_members(self) -> dict[str, Any]:
        entry_soup = self.fetch(ENTRY_URL)
        grid_url = self.resolve_grid_url(entry_soup)
        committee_url = self.resolve_committee_pdf_url()
        roster_urls = self.resolve_roster_pdf_urls()

        grid_pdf = self.fetch_pdf(grid_url)
        grid_members, district_checks = self.parse_grid_pdf(grid_pdf)

        roster_members, omitted_roster_members = self.parse_roster_pdfs(roster_urls)
        self.check_roster_matches_grid(roster_members, grid_members)

        committees_by_name, committee_checks = self.parse_committee_pdf(
            self.fetch_pdf(committee_url)
        )

        members: list[dict[str, Any]] = []
        for name, grid_info in grid_members.items():
            roster_info = roster_members[name]
            committees = list(committees_by_name.get(name, {}).get("committees", []))
            positions = list(committees_by_name.get(name, {}).get("positions", []))
            for position in roster_info.get("positions", []):
                add_unique(positions, str(position))

            slug = make_slug(kana_to_katakana(str(roster_info.get("name_kana") or "")), name)
            member = {
                "id": f"{COUNCIL_ID}--{slug}",
                "council_id": COUNCIL_ID,
                "name": name,
                "name_kana": roster_info.get("name_kana"),
                "district": grid_info["district"],
                "faction": grid_info["faction"],
                "elected_count": grid_info["elected_count"],
                "positions": positions,
                "committees": committees,
                "photo_url": None,
                "official_profile_url": None,
            }
            members.append(member)

        capacity_total = sum(int(item["capacity"]) for item in district_checks)
        vacancies = sum(int(item["vacancies"]) for item in district_checks)
        if capacity_total != EXPECTED_CAPACITY:
            raise RuntimeError(f"capacity total {capacity_total} != {EXPECTED_CAPACITY}")
        if len(district_checks) != EXPECTED_DISTRICTS:
            raise RuntimeError(
                f"district count {len(district_checks)} != {EXPECTED_DISTRICTS}"
            )
        if capacity_total - len(members) != vacancies:
            raise RuntimeError(
                f"vacancy total mismatch: {capacity_total} - {len(members)} != {vacancies}"
            )

        vacancy_details = [
            {
                "district": item["district"],
                "ketsuin": item["vacancies"],
                "source_url": grid_url,
            }
            for item in district_checks
            if int(item["vacancies"]) > 0
        ]

        payload: dict[str, Any] = {
            "council_id": COUNCIL_ID,
            "source_url": ENTRY_URL,
            "source_name": "北海道議会 議員名簿",
            "acquisition": "scraping",
            "members": members,
            "checks": {
                "source_shape": "pdf_member_roster",
                "pdf_index_url": PDF_INDEX_URL,
                "grid_source_url": grid_url,
                "committee_source_url": committee_url,
                "roster_pdf_count": len(roster_urls),
                "roster_pdf_urls": roster_urls,
                "district_count": len(district_checks),
                "expected_district_count": EXPECTED_DISTRICTS,
                "expected_capacity": EXPECTED_CAPACITY,
                "capacity_total": capacity_total,
                "parsed_roster_members": len(roster_members),
                "parsed_grid_members": len(grid_members),
                "parsed_members": len(members),
                "omitted_roster_members": omitted_roster_members,
                "districts": district_checks,
                "committee_checks": committee_checks,
                "two_source_reconciliation": {
                    "roster_minus_grid": [],
                    "grid_minus_roster": [],
                    "faction_district_elected_count_mismatches": [],
                },
                "notes": [
                    "50音PDF群から氏名・かな・会派・選挙区・当選回数のみを許可リスト抽出",
                    "住所・電話・FAX・メール・個人URL・自己PRは保存しない",
                    "辞職・逝去注記の旧議員は現職集合から除外",
                    "選挙区別・会派別PDFを件数検算アンカーとして使用",
                    "写真は取得せず、photo_urlは全員null",
                ],
            },
        }
        force_photo_null(payload)
        apply_member_contract(
            payload,
            teisu=capacity_total,
            source_basis_date=SOURCE_BASIS_DATE,
            vacancy_details=vacancy_details,
            anchor_source_url=grid_url,
            anchor_type="official_pdf_district_faction_grid",
            notes=[
                "50音PDF群と選挙区別・会派別PDFの氏名集合・会派・選挙区・当選回数を照合",
            ],
        )
        return payload

    def resolve_roster_pdf_urls(self) -> list[str]:
        soup = self.fetch(PDF_INDEX_URL)
        urls: list[str] = []
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            if not href.lower().endswith(".pdf") or "32meibo" not in href:
                continue
            url = urljoin(PDF_INDEX_URL, href)
            if url not in urls:
                urls.append(url)
        if len(urls) != 8:
            raise RuntimeError(f"expected 8 roster PDFs, found {len(urls)}: {urls}")
        return urls

    def resolve_grid_url(self, soup: BeautifulSoup) -> str:
        for link in soup.find_all("a", href=True):
            label = normalize_text(link.get_text(" ", strip=True))
            if "選挙区別・会派別議員一覧" in label and str(link["href"]).endswith(".pdf"):
                return urljoin(ENTRY_URL, str(link["href"]))
        raise RuntimeError("district/faction grid PDF link not found")

    def resolve_committee_pdf_url(self) -> str:
        soup = self.fetch(COMMITTEE_INDEX_URL)
        for link in soup.find_all("a", href=True):
            label = normalize_text(link.get_text(" ", strip=True))
            if "後期委員名簿" in label and str(link["href"]).endswith(".pdf"):
                return urljoin(COMMITTEE_INDEX_URL, str(link["href"]))
        raise RuntimeError("committee PDF link not found")

    def fetch_pdf(self, url: str) -> bytes:
        response = self.session.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
            raise RuntimeError(f"{url}: response is not PDF ({content_type})")
        time.sleep(self.sleep_seconds)
        return response.content

    def parse_grid_pdf(
        self, pdf_bytes: bytes
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            tables = pdf.pages[0].extract_tables()
        if not tables:
            raise RuntimeError("district/faction grid table not found")
        table = tables[0]
        header = [normalize_text(cell) for cell in table[0]]
        if header[2:] != FACTIONS:
            raise RuntimeError(f"unexpected faction columns: {header[2:]}")

        members: dict[str, dict[str, Any]] = {}
        district_checks: list[dict[str, Any]] = []
        previous_prefix = ""
        for row in table[1:]:
            if not row or not row[0]:
                continue
            raw_district = normalize_text(row[0])
            if not raw_district or raw_district.startswith("計"):
                continue
            if raw_district.startswith("〃"):
                district = previous_prefix + raw_district.replace("〃", "")
            else:
                district = raw_district
                if " " in raw_district:
                    previous_prefix = raw_district.split(" ", 1)[0]
            district = compact_name(district)
            capacity = parse_count(row[1]) or 0
            district_names: list[str] = []
            for index, cell in enumerate(row[2:], start=2):
                faction = header[index]
                text = normalize_text(cell)
                if not text:
                    continue
                for match in GRID_MEMBER_RE.finditer(text):
                    name = compact_name(match.group("name"))
                    if not name or name.startswith("※"):
                        continue
                    if name in members:
                        raise RuntimeError(f"duplicate grid member: {name}")
                    members[name] = {
                        "name": name,
                        "district": district,
                        "faction": faction,
                        "elected_count": int(match.group("count")),
                    }
                    district_names.append(name)
            if len(district_names) > capacity:
                raise RuntimeError(
                    f"{district}: member count {len(district_names)} exceeds capacity {capacity}"
                )
            district_checks.append(
                {
                    "district": district,
                    "capacity": capacity,
                    "members": len(district_names),
                    "vacancies": capacity - len(district_names),
                    "names": district_names,
                }
            )
        return members, district_checks

    def parse_roster_pdfs(
        self, urls: list[str]
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
        members: dict[str, dict[str, Any]] = {}
        omitted: list[dict[str, str]] = []
        for url in urls:
            pdf_bytes = self.fetch_pdf(url)
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_index, page in enumerate(pdf.pages, start=1):
                    halves = [
                        (0, 0, page.width / 2, page.height),
                        (page.width / 2, 0, page.width, page.height),
                    ]
                    for half_index, bbox in enumerate(halves, start=1):
                        text = page.crop(bbox).extract_text(layout=False) or ""
                        for block in self.split_roster_blocks(text):
                            name = block["name"]
                            lines = block["lines"]
                            if any(word in line for word in CURRENT_EXCLUDE_WORDS for line in lines):
                                omitted.append(
                                    {
                                        "name": name,
                                        "reason": "辞職/逝去注記",
                                        "source_url": url,
                                    }
                                )
                                continue
                            parsed = self.parse_roster_block(block)
                            if parsed is None:
                                continue
                            if name in members:
                                raise RuntimeError(f"duplicate roster member: {name}")
                            parsed["source_url"] = url
                            parsed["page"] = page_index
                            parsed["half"] = half_index
                            members[name] = parsed
        return members, omitted

    def split_roster_blocks(self, text: str) -> list[dict[str, Any]]:
        lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
        blocks: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for line in lines:
            match = NAME_LINE_RE.match(line)
            if match:
                name = compact_name(match.group("name"))
                # Column crops and contact zones can leave fragments that look
                # like name lines. Do not let them terminate the current block.
                if name in {"北海道議会", "員名簿", "名簿", "た"}:
                    if current is not None:
                        current["lines"].append(line)
                    continue
                if current is not None:
                    blocks.append(current)
                current = {
                    "name": name,
                    "name_kana": normalize_text(match.group("kana")),
                    "lines": [],
                }
            elif current is not None:
                current["lines"].append(line)
        if current is not None:
            blocks.append(current)
        return blocks

    def parse_roster_block(self, block: dict[str, Any]) -> dict[str, Any] | None:
        faction = None
        district = None
        elected_count = None
        positions: list[str] = []
        for line in block["lines"][:8]:
            if line.endswith("選出"):
                for candidate in FACTIONS:
                    if line.startswith(candidate):
                        faction = candidate
                        district = compact_name(line[len(candidate) :].removesuffix("選出"))
                        break
            count_match = re.search(r"当選\s*([0-9一二三四五六七八九十]+)\s*回", line)
            if count_match:
                elected_count = parse_count(count_match.group(1))
            if line in {"議長", "副議長"}:
                add_unique(positions, line)

        if faction is None or district is None or elected_count is None:
            return None
        return {
            "name": block["name"],
            "name_kana": block["name_kana"],
            "faction": faction,
            "district": district,
            "elected_count": elected_count,
            "positions": positions,
        }

    def check_roster_matches_grid(
        self,
        roster_members: dict[str, dict[str, Any]],
        grid_members: dict[str, dict[str, Any]],
    ) -> None:
        roster_names = set(roster_members)
        grid_names = set(grid_members)
        roster_minus_grid = sorted(roster_names - grid_names)
        grid_minus_roster = sorted(grid_names - roster_names)
        if roster_minus_grid or grid_minus_roster:
            raise RuntimeError(
                "roster/grid name mismatch: "
                f"roster_minus_grid={roster_minus_grid}, grid_minus_roster={grid_minus_roster}"
            )

        mismatches: list[dict[str, Any]] = []
        for name in sorted(grid_names):
            roster = roster_members[name]
            grid = grid_members[name]
            for key in ("district", "faction", "elected_count"):
                if roster.get(key) != grid.get(key):
                    mismatches.append(
                        {
                            "name": name,
                            "field": key,
                            "roster": roster.get(key),
                            "grid": grid.get(key),
                        }
                    )
        if mismatches:
            raise RuntimeError(f"roster/grid metadata mismatch: {mismatches}")

    def parse_committee_pdf(
        self, pdf_bytes: bytes
    ) -> tuple[dict[str, dict[str, list[str]]], dict[str, Any]]:
        committees_by_name: dict[str, dict[str, list[str]]] = {}
        table_count = 0
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:2]:
                for table in page.extract_tables():
                    table_count += 1
                    self.parse_committee_table(table, committees_by_name)
        return committees_by_name, {
            "source_shape": "committee_pdf_tables",
            "table_count": table_count,
            "members_with_committee_entries": len(committees_by_name),
            "parsed_pages": 2,
            "note": "令和8年3月9日現在の常任委員会・議会運営委員会・特別委員会を抽出。予算/決算の会期別委員会ページは除外。",
        }

    def parse_committee_table(
        self,
        table: list[list[str | None]],
        committees_by_name: dict[str, dict[str, list[str]]],
    ) -> None:
        if not table or len(table) < 5:
            return
        first = normalize_text(table[0][0])
        if first == "委 員 会 名":
            committee_names = [normalize_committee_name(cell) for cell in table[0][1:]]
            role_rows = [
                ("委員長", table[2][1:]),
                ("副委員長", table[3][1:]),
                ("委員", table[4][1:]),
            ]
        else:
            committee_names = [normalize_committee_name(cell) for cell in table[0]]
            role_rows = [
                ("委員長", table[2]),
                ("副委員長", table[3]),
                ("委員", table[4]),
            ]

        for role, cells in role_rows:
            for committee, cell in zip(committee_names, cells):
                if not committee or not cell:
                    continue
                for name in self.extract_committee_member_names(cell):
                    entry = committees_by_name.setdefault(
                        name,
                        {"committees": [], "positions": []},
                    )
                    add_unique(entry["committees"], committee)
                    if role == "委員長":
                        add_unique(entry["positions"], f"{committee} 委員長")
                    elif role == "副委員長":
                        add_unique(entry["positions"], f"{committee} 副委員長")

    def extract_committee_member_names(self, cell: str | None) -> list[str]:
        names: list[str] = []
        for line in str(cell or "").splitlines():
            if "欠員" in line:
                continue
            for match in COMMITTEE_NAME_RE.finditer(normalize_text(line)):
                name = compact_name(match.group("name"))
                if name:
                    add_unique(names, name)
        return names


def main() -> int:
    scraper = HokkaidoPrefScraper()
    data = scraper.scrape_members()
    scraper.save_json(OUT_PATH, data)
    print(f"{len(data['members'])} members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
