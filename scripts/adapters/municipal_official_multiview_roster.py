"""Official municipal council roster adapter for designated cities.

The designated-city phase uses official CMS pages, not the minutes vendors.
This adapter keeps one shared request/output/count-check contract and isolates
city-specific view parsing in allowlist functions. Profile/contact-rich pages are
parsed only for explicitly listed roster fields.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.single_page_roster import (  # noqa: E402
    build_member,
    compact_kana_text,
    compact_name,
    ensure_unique_ids,
    expand_table,
    normalize_text,
    parse_count,
    text_lines,
)
from scripts.base import CouncilScraperBase  # noqa: E402
from scripts.lib.member_contract import apply_member_contract, force_photo_null  # noqa: E402

OUT_DIR = REPO_ROOT / "docs" / "data"

KANA_RE = re.compile(r"^[ぁ-ゖァ-ヺー・\s]+$")
DISTRICT_RE = re.compile(r"[一-龥ぁ-ゖァ-ヺー・々ヶヵ]+区$")
SKIP_MEMBER_NAMES = {"", "-", "ー", "－", "―", "−"}
WINDOW_NOTICE_RE = re.compile(r"（?別(?:ウインドウ|ウィンドウ)で開く）?")


def out_path(council_id: str) -> Path:
    return OUT_DIR / council_id / "members.json"


def add_unique(items: list[str], value: str | None) -> None:
    text = normalize_text(value)
    if text and text not in items:
        items.append(text)


def is_kana(value: str) -> bool:
    return bool(value) and KANA_RE.fullmatch(value) is not None


def clean_member_name(value: str | None) -> str:
    text = normalize_text(value)
    text = WINDOW_NOTICE_RE.sub("", text)
    text = re.sub(r"議員$", "", text).strip()
    text = re.sub(r"（(?:議長|副議長)）", "", text)
    text = text.replace("\u3000", " ")
    return normalize_text(text)


def split_name_kana(text: str) -> tuple[str, str | None]:
    value = clean_member_name(text)
    value = value.replace("発言", "")
    paren = re.search(r"^(.+?)[（(]\s*([^（）()]+?)\s*[）)]", value)
    if paren:
        return compact_name(paren.group(1)), compact_kana_text(paren.group(2))
    tokens = normalize_text(value).split()
    if not tokens:
        return "", None
    if is_kana(tokens[0]):
        split_at = 0
        while split_at < len(tokens) and is_kana(tokens[split_at]):
            split_at += 1
        # Some official rosters write both reading and display name in kana
        # (e.g. "こじま ゆみ こじま ゆみ"). In that case keep the latter
        # half as the display name instead of dropping the member.
        if split_at == len(tokens) and len(tokens) >= 2:
            half = len(tokens) // 2
            kana = " ".join(tokens[:half])
            name = " ".join(tokens[half:])
            return compact_name(name), compact_kana_text(kana)
        kana = " ".join(tokens[:split_at])
        name = " ".join(tokens[split_at:])
        return compact_name(name), compact_kana_text(kana)
    for index, token in enumerate(tokens):
        if is_kana(token):
            return compact_name(" ".join(tokens[:index])), compact_kana_text(" ".join(tokens[index:]))
    # Sagamihara/Kitakyushu sometimes render name and kana on separate lines that
    # have already been paired by the caller. If no kana marker exists, keep name.
    return compact_name(value), None


def parse_name_and_kana_from_pair(name: str, kana: str | None) -> tuple[str, str | None]:
    parsed_name, parsed_kana = split_name_kana(name)
    return parsed_name, compact_kana_text(kana) or parsed_kana


def committee_tokens(value: str | None) -> list[str]:
    text = normalize_text(value)
    if not text or text in {"-", "なし"}:
        return []
    text = text.replace("、", " / ").replace("・", "・")
    parts = re.split(r"\s*/\s*|\s+", text)
    result: list[str] = []
    for part in parts:
        part = normalize_text(part)
        if not part or part in {"委員長", "副委員長"}:
            continue
        if "委員" in part or "委員会" in part or part.endswith("特別") or part.endswith("会"):
            add_unique(result, part)
    return result


def positions_from_text(value: str | None) -> list[str]:
    text = normalize_text(value)
    result: list[str] = []
    for role in ("議長", "副議長"):
        if role in text:
            add_unique(result, role)
    for match in re.finditer(r"([^\s、/]+委員会?)\s*〔?(副?委員長)〕?", text):
        add_unique(result, f"{match.group(1)} {match.group(2)}")
    if "委員長" in text and "委員会" in text:
        # Sapporo style: 総務委員会副委員長 / ...委員会委員長
        for chunk in re.split(r"\s+|、|/", text):
            if "委員会" in chunk and "委員長" in chunk:
                role = "副委員長" if "副委員長" in chunk else "委員長"
                name = chunk.replace("副委員長", "").replace("委員長", "")
                add_unique(result, f"{name} {role}")
    return result


def make_member(
    *,
    council_id: str,
    name: str,
    kana: str | None = None,
    district: str | None = None,
    faction: str | None = None,
    elected_count: int | None = None,
    profile_url: str | None = None,
    committees: list[str] | None = None,
    positions: list[str] | None = None,
) -> dict[str, Any] | None:
    clean_name = compact_name(name)
    if clean_name in SKIP_MEMBER_NAMES:
        return None
    return build_member(
        council_id=council_id,
        name=clean_name,
        kana=compact_kana_text(kana),
        district=normalize_text(district) or None,
        faction=normalize_text(faction) or None,
        elected_count=elected_count,
        profile_url=profile_url,
        committees=committees or [],
        positions=positions or [],
    )


def capacity_from_heading(text: str) -> tuple[str, int | None, int]:
    label = normalize_text(text)
    district = re.split(r"[（(]", label, maxsplit=1)[0].strip()
    capacity_match = re.search(r"(?:定数|定員|議員定数)\s*([0-9０-９一二三四五六七八九十]+)\s*(?:人|名)?", label)
    if not capacity_match:
        capacity_match = re.search(r"[（(]\s*([0-9０-９一二三四五六七八九十]+)\s*(?:人|名)\s*[）)]", label)
    vacancy_match = re.search(r"欠員\s*([0-9０-９一二三四五六七八九十]+)", label)
    return district, parse_count(capacity_match.group(1)) if capacity_match else None, parse_count(vacancy_match.group(1)) or 0 if vacancy_match else 0


def root_payload(config: dict[str, Any], members: list[dict[str, Any]], vacancy_details: list[dict[str, Any]] | None = None, teisu: int | None = None, notes: list[str] | None = None) -> dict[str, Any]:
    ensure_unique_ids(members)
    payload: dict[str, Any] = {
        "council_id": config["council_id"],
        "source_url": config["source_url"],
        "source_name": config.get("source_name", config["name"]),
        "acquisition": "scraping",
        "members": members,
    }
    force_photo_null(payload)
    apply_member_contract(
        payload,
        teisu=teisu or config["teisu"],
        source_basis_date=config.get("source_basis_date", "公式基準日記載なし"),
        vacancy_details=vacancy_details or config.get("vacancy_details", []),
        anchor_source_url=config.get("anchor_source_url", config["source_url"]),
        anchor_type=config.get("anchor_type", "official_district_capacity"),
        notes=[
            "公式CMSの名簿ビューから氏名・ふりがな・会派・行政区・当選回数・委員会・役職のみを許可リスト抽出",
            "許可外項目は保存しない",
            "写真は取得せず、photo_urlは全員null",
            *(notes or config.get("notes", [])),
        ],
    )
    return payload


class MunicipalOfficialMultiviewScraper(CouncilScraperBase):
    def fetch_soup(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        time.sleep(self.sleep_seconds)
        return BeautifulSoup(response.text, "html.parser")

    def scrape_members(self, city_id: str) -> dict[str, Any]:
        config = CITY_CONFIGS[city_id]
        return PARSERS[config["parser"]](self, config)


def parse_sapporo(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members: list[dict[str, Any]] = []
    teisu = 0
    district_counts: dict[str, int] = {}
    capacities: dict[str, int] = {}
    for h2 in soup.find_all("h2"):
        district, capacity, _ = capacity_from_heading(h2.get_text(" ", strip=True))
        if not district or capacity is None:
            continue
        teisu += capacity
        capacities[district] = capacity
        table = h2.find_next("table")
        if not table:
            continue
        for cell in table.find_all("td"):
            lines = text_lines(cell)
            if not lines:
                continue
            text = normalize_text(" ".join(lines))
            m = re.match(r"^(?P<pre>.+?)\s*[（(](?P<faction>.+?)・\s*(?P<count>[0-9０-９一二三四五六七八九十]+)\s*期[）)]\s*(?P<rest>.*)$", text)
            if not m:
                continue
            name, kana = split_name_kana(m.group("pre"))
            rest = m.group("rest")
            member = make_member(
                council_id=config["council_id"],
                name=name,
                kana=kana,
                district=district,
                faction=m.group("faction"),
                elected_count=parse_count(m.group("count")),
                committees=committee_tokens(rest),
                positions=positions_from_text(rest),
            )
            if member:
                members.append(member)
                district_counts[district] = district_counts.get(district, 0) + 1
    if teisu != config["teisu"]:
        raise RuntimeError(f"Sapporo capacity total {teisu} != {config['teisu']}")
    vacancy_details = []
    for district, capacity in capacities.items():
        missing = capacity - district_counts.get(district, 0)
        if missing < 0:
            raise RuntimeError(f"{district}: parsed members exceed capacity")
        if missing:
            vacancy_details.append({"district": district, "ketsuin": missing, "source_url": config["source_url"]})
    return root_payload(config, members, teisu=teisu, vacancy_details=vacancy_details)


def parse_simple_table(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = expand_table(table)
        if not rows:
            continue
        headers = [normalize_text(cell.get_text(" ", strip=True)) for cell in rows[0]]
        for cells in rows[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if not any(values):
                continue
            member = parse_table_row(config, headers, cells, values)
            if member:
                members.append(member)
    return root_payload(config, members)


def parse_table_row(config: dict[str, Any], headers: list[str], cells: list[Tag], values: list[str]) -> dict[str, Any] | None:
    cid = config["council_id"]
    kind = config["table_kind"]
    if kind == "chiba":
        if len(values) < 4 or "氏名" in values[1]:
            return None
        name, kana = split_name_kana(values[1])
        return make_member(council_id=cid, name=name, kana=kana, district=values[2], faction=values[3])
    if kind == "shizuoka":
        if len(values) < 4 or values[1] == "氏名":
            return None
        name, kana = split_name_kana(values[1])
        return make_member(council_id=cid, name=name, kana=kana, district=values[3], faction=values[2])
    if kind == "nagoya":
        if len(values) < 5 or values[0] == "名前":
            return None
        return make_member(council_id=cid, name=values[0], kana=values[1], faction=values[2], district=values[3], committees=committee_tokens(values[4]), positions=positions_from_text(values[4]))
    if kind == "kyoto":
        if len(values) < 3 or values[0] == "名前":
            return None
        return make_member(council_id=cid, name=values[0], faction=values[1], district=values[2])
    if kind == "sakai":
        if len(values) < 6 or values[1] == "氏名":
            return None
        return make_member(council_id=cid, name=values[1], kana=values[2], district=values[3], faction=values[4], committees=committee_tokens(values[5]))
    if kind == "hiroshima":
        if len(values) < 4 or values[0] == "議員名":
            return None
        name, positions = re.sub(r"（.*?）", "", values[0]), positions_from_text(values[0])
        return make_member(council_id=cid, name=name, kana=values[1], district=values[2], faction=values[3], positions=positions)
    if kind == "kumamoto":
        if len(values) < 3 or values[0] == "議員名":
            return None
        return make_member(council_id=cid, name=values[0], faction=values[1], committees=committee_tokens(values[2]), positions=positions_from_text(values[2]))
    return None


def parse_fukuoka(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    table = soup.select_one("table.tablepress") or soup.find("table")
    if table is None:
        raise RuntimeError("Fukuoka member table not found")
    members = []
    for cells in expand_table(table)[1:]:
        values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
        if len(values) < 4 or values[1] == "氏名":
            continue
        link = cells[1].find("a", href=True)
        member = make_member(
            council_id=config["council_id"],
            name=values[1],
            district=values[2],
            faction=values[3],
            profile_url=urljoin(config["source_url"], link["href"]) if link else None,
        )
        if member:
            members.append(member)
    return root_payload(config, members)


def parse_saitama(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members = []
    for link in soup.select("ul.member_list li a[href]"):
        name = normalize_text((link.select_one(".name") or link).get_text(" ", strip=True))
        kana = normalize_text((link.select_one(".ruby") or Tag(name="span")).get_text(" ", strip=True))
        data = {}
        for row in link.select(".text_area .cf"):
            label = normalize_text((row.select_one(".text_ttl") or row).get_text(" ", strip=True))
            value = normalize_text((row.select_one(".text_cont") or row).get_text(" ", strip=True))
            data[label] = value
        member = make_member(
            council_id=config["council_id"],
            name=name,
            kana=kana,
            district=data.get("選出区"),
            faction=data.get("所属会派"),
            profile_url=urljoin(config["source_url"], link["href"]),
        )
        if member:
            members.append(member)
    return root_payload(config, members)


def parse_yokohama(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [normalize_text(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]
            if not cells:
                continue
            text = cells[-1]
            first = re.search(r"(.+?[）)])\s*[（(](.+?区)\s*[）)]", text)
            if not first:
                continue
            name, kana = split_name_kana(first.group(1))
            tail = first.group(2)
            parts = tail.split()
            district = parts[-1] if parts and parts[-1].endswith("区") else None
            faction = normalize_text(" ".join(parts[:-1])) if district else tail
            member = make_member(council_id=config["council_id"], name=name, kana=kana, district=district, faction=faction)
            if member:
                members.append(member)
    return root_payload(config, members)


def parse_sendai(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    members_by_name: dict[str, dict[str, Any]] = {}
    for district, url in config["district_urls"].items():
        soup = scraper.fetch_soup(url)
        for link in soup.select("ul.page_list a[href]"):
            name = compact_name(link.get_text(" ", strip=True))
            member = make_member(council_id=config["council_id"], name=name, district=district, profile_url=urljoin(url, link["href"]))
            if member:
                members_by_name[member["name"]] = member
    # Merge factions from party pages; these pages contain no contact data.
    for faction, url in discover_sendai_party_pages(scraper, config).items():
        soup = scraper.fetch_soup(url)
        body = soup.find("article") or soup.find(id="main") or soup
        lines = text_lines(body)
        for line in lines:
            name = compact_name(line)
            if name in members_by_name:
                members_by_name[name]["faction"] = faction
    return root_payload(config, list(members_by_name.values()))


def discover_sendai_party_pages(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, str]:
    soup = scraper.fetch_soup(config["party_index_url"])
    result = {}
    for link in soup.select("article a[href], #main a[href]"):
        label = normalize_text(link.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if label and href.startswith("kaiha") and href.endswith(".html"):
            result[label] = urljoin(config["party_index_url"], href)
    return result


def parse_kawasaki(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    index = scraper.fetch_soup(config["source_url"])
    profile_urls: list[str] = []
    for link in index.select('a[href*="/980/page/"]'):
        href = urljoin(config["source_url"], link["href"])
        if href not in profile_urls:
            profile_urls.append(href)
    if not profile_urls:
        subcategory_urls = []
        for link in index.select('a[href*="category/40-3-1-"]'):
            url = urljoin(config["source_url"], link["href"])
            if url not in subcategory_urls and url != config["source_url"]:
                subcategory_urls.append(url)
        for url in subcategory_urls:
            soup = scraper.fetch_soup(url)
            for link in soup.select('a[href*="/980/page/"]'):
                href = urljoin(url, link["href"])
                if href not in profile_urls:
                    profile_urls.append(href)
    members = []
    for url in profile_urls:
        soup = scraper.fetch_soup(url)
        title = normalize_text((soup.find("h1") or soup.find("title") or soup).get_text(" ", strip=True))
        m = re.search(r"([^（(]+)[（(]([^）)]+)[）)]", title)
        if not m:
            continue
        name, kana = compact_name(m.group(1).replace("川崎市 :", "")), compact_kana_text(m.group(2))
        content = soup.find(id="content") or soup.find(id="main") or soup
        text = normalize_text(content.get_text(" ", strip=True))
        info = re.search(r"[（(]([^・）)]+)・([^）)]+)[）)]\s*当選回数\s*([0-9０-９一二三四五六七八九十]+)\s*回", text)
        committees = []
        if "・所属委員会" in text:
            after = text.split("・所属委員会", 1)[1].split("・連絡先", 1)[0]
            committees = committee_tokens(after)
        member = make_member(
            council_id=config["council_id"],
            name=name,
            kana=kana,
            district=info.group(1) if info else None,
            faction=info.group(2) if info else None,
            elected_count=parse_count(info.group(3)) if info else None,
            profile_url=url,
            committees=committees,
        )
        if member:
            members.append(member)
    return root_payload(config, members)


def parse_sagamihara(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members = []
    seen = set()
    for table in soup.find_all("table"):
        for cell in table.find_all("td"):
            lines = text_lines(cell)
            # Cells can contain one or two name/kana pairs.
            idx = 0
            while idx < len(lines) - 1:
                name_line = lines[idx]
                kana_line = lines[idx + 1]
                if is_kana(kana_line.replace(" ", "")) or re.fullmatch(r"[ぁ-ゖ]+", kana_line.replace(" ", "")):
                    name, kana = parse_name_and_kana_from_pair(name_line, kana_line)
                    key = (name, kana)
                    if name and key not in seen:
                        seen.add(key)
                        member = make_member(council_id=config["council_id"], name=name, kana=kana)
                        if member:
                            members.append(member)
                    idx += 2
                else:
                    idx += 1
    return root_payload(config, members)


def parse_niigata(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members = []
    capacities: dict[str, int] = {}
    vacancies: dict[str, int] = {}
    district = None
    for node in (soup.find("main") or soup).find_all(["h3", "div"]):
        if node.name == "h3":
            district, cap, vacancy = capacity_from_heading(node.get_text(" ", strip=True))
            if district and cap:
                capacities[district] = cap
                vacancies[district] = vacancy
            continue
        if district and "img-area-l" in (node.get("class") or []):
            lines = text_lines(node)
            try:
                index = lines.index("氏名・会派")
            except ValueError:
                continue
            name = lines[index + 1] if index + 1 < len(lines) else ""
            faction = lines[index + 2].lstrip("・") if index + 2 < len(lines) else None
            member = make_member(council_id=config["council_id"], name=name, district=district, faction=faction)
            if member:
                members.append(member)
    vacancy_details = [{"district": d, "ketsuin": k, "source_url": config["source_url"]} for d, k in vacancies.items() if k]
    return root_payload(config, members, teisu=sum(capacities.values()), vacancy_details=vacancy_details)


def parse_osaka(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    index = scraper.fetch_soup(config["source_url"])
    district_links = []
    for link in index.select('a[href*="/shikai/page/"]'):
        label = normalize_text(link.get_text(" ", strip=True))
        if label.endswith("区"):
            url = urljoin(config["source_url"], link["href"])
            if (label, url) not in district_links:
                district_links.append((label, url))
    members = []
    capacities = {}
    for district, url in district_links:
        soup = scraper.fetch_soup(url)
        lines = text_lines(soup)
        capacity = None
        for line in lines:
            if district in line and "定員" in line:
                _, capacity, _ = capacity_from_heading(line)
                break
        if capacity:
            capacities[district] = capacity
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.endswith("議員") and "名簿" not in line and len(line) < 30:
                display = clean_member_name(line)
                detail = lines[i + 1] if i + 1 < len(lines) else display
                name, kana = split_name_kana(detail if "（" in detail or "(" in detail else display)
                block = []
                j = i + 1
                while j < len(lines) and not (j > i + 1 and lines[j].endswith("議員") and "名簿" not in lines[j] and len(lines[j]) < 30):
                    block.append(lines[j])
                    j += 1
                block_text = " ".join(block)
                faction = None
                m_f = re.search(r"所属会派[:：]\s*([^\s]+)", block_text)
                if m_f:
                    faction = m_f.group(1)
                elected = None
                m_e = re.search(r"期数[:：]\s*([0-9０-９一二三四五六七八九十]+)\s*期", block_text)
                if m_e:
                    elected = parse_count(m_e.group(1))
                committees = []
                for item in block:
                    if "委員" in item and not any(x in item for x in ("連絡", "作成者", "お問い合わせ")):
                        committees.extend(committee_tokens(item))
                member = make_member(council_id=config["council_id"], name=name, kana=kana, district=district, faction=faction, elected_count=elected, committees=committees, positions=positions_from_text(block_text), profile_url=url)
                if member:
                    members.append(member)
                i = j
            else:
                i += 1
    return root_payload(config, members, teisu=sum(capacities.values()) or config["teisu"])



def parse_hamamatsu(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    table = soup.find("table")
    if table is None:
        raise RuntimeError("Hamamatsu member table not found")
    members = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 6:
            continue
        values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
        name, kana = split_name_kana(values[0])
        committees = committee_tokens(values[1]) + committee_tokens(values[2])
        positions = positions_from_text(values[1]) + positions_from_text(values[2])
        member = make_member(
            council_id=config["council_id"],
            name=name,
            kana=kana,
            district=values[4],
            faction=values[5],
            committees=committees,
            positions=positions,
        )
        if member:
            members.append(member)
    return root_payload(config, members)

def parse_kobe(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    members = []
    capacities = {}
    district_counts: dict[str, int] = {}
    for district, url in config["district_urls"].items():
        soup = scraper.fetch_soup(url)
        heading = soup.find("h2")
        if heading:
            _, capacity, _ = capacity_from_heading(heading.get_text(" ", strip=True))
            if capacity:
                capacities[district] = capacity
        for ul in soup.select("ul.noicon"):
            data: dict[str, str] = {}
            for li in ul.find_all("li", recursive=False):
                text = normalize_text(li.get_text(" ", strip=True))
                m = re.match(r"[\u3000\s]*\((\d)\)\s*(.+)$", text)
                if m and m.group(1) in {"1", "2", "3", "4"}:
                    data[m.group(1)] = m.group(2)
            if "1" not in data:
                continue
            name, kana = split_name_kana(data["1"])
            member = make_member(council_id=config["council_id"], name=name, kana=kana, district=district, faction=data.get("2"), elected_count=parse_count(data.get("3")), committees=committee_tokens(data.get("4")), profile_url=url)
            if member:
                members.append(member)
                district_counts[district] = district_counts.get(district, 0) + 1
    vacancy_details = []
    for district, capacity in capacities.items():
        missing = capacity - district_counts.get(district, 0)
        if missing < 0:
            raise RuntimeError(f"{district}: parsed members exceed capacity")
        if missing:
            vacancy_details.append({"district": district, "ketsuin": missing, "source_url": config["district_urls"][district]})
    return root_payload(config, members, teisu=sum(capacities.values()) or config["teisu"], vacancy_details=vacancy_details)


def parse_okayama(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members = []
    seen = set()
    for link in soup.find_all("a", href=True):
        text = normalize_text(link.get_text(" ", strip=True))
        m = re.match(r"(.+?[）)])\s*([^\s]+区)$", text)
        if not m:
            continue
        name, kana = split_name_kana(m.group(1))
        key = (name, m.group(2))
        if key in seen:
            continue
        seen.add(key)
        member = make_member(council_id=config["council_id"], name=name, kana=kana, district=m.group(2), profile_url=urljoin(config["source_url"], link["href"]))
        if member:
            members.append(member)
    return root_payload(config, members)


def parse_kitakyushu(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    index = scraper.fetch_soup(config["district_index_url"])
    links = []
    for link in index.select('a[href*="file_"]'):
        label = normalize_text(link.get_text(" ", strip=True))
        if label.endswith("区"):
            links.append((label, urljoin(config["district_index_url"], link["href"])))
    members = []
    capacities = {}
    for district, url in links:
        soup = scraper.fetch_soup(url)
        text = normalize_text((soup.find("h1") or soup).get_text(" ", strip=True))
        for h in soup.find_all(["h1", "h2", "h3"]):
            if district in h.get_text(" ", strip=True):
                _, cap, _ = capacity_from_heading(h.get_text(" ", strip=True))
                if cap:
                    capacities[district] = cap
        for table in soup.find_all("table"):
            lines = text_lines(table)
            if len(lines) < 3:
                continue
            name = lines[0]
            faction = lines[1]
            elected = parse_count(lines[2])
            committees = []
            for line in lines[3:]:
                if "連絡" in line or "住所" in line or "電話" in line or "メール" in line or "ホームページ" in line or "生" in line:
                    continue
                committees.extend(committee_tokens(line))
            member = make_member(council_id=config["council_id"], name=name, district=district, faction=faction, elected_count=elected, committees=committees, profile_url=url)
            if member:
                members.append(member)
    return root_payload(config, members, teisu=sum(capacities.values()) or config["teisu"])


def parse_tokyo_ward_links(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    """Parse Tokyo ward rosters whose official page exposes member profile links."""
    soup = scraper.fetch_soup(config["source_url"])
    members: list[dict[str, Any]] = []
    seen: set[str] = set()
    href_re = re.compile(config["member_href_re"])
    for link in soup.find_all("a", href=True):
        href = str(link.get("href", ""))
        full_url = urljoin(config["source_url"], href)
        if not href_re.search(href) and not href_re.search(full_url):
            continue
        label = clean_member_name(link.get_text(" ", strip=True))
        if not label or label in config.get("exclude_labels", []):
            continue
        name, kana = split_name_kana(label)
        key = full_url
        if key in seen:
            continue
        seen.add(key)
        member = make_member(
            council_id=config["council_id"],
            name=name,
            kana=kana,
            district=config["district"],
            profile_url=full_url,
        )
        if member:
            members.append(member)
    return root_payload(config, members)


def parse_tokyo_ward_table(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    """Parse contact-rich ward tables by reading only allowlisted columns."""
    soup = scraper.fetch_soup(config["source_url"])
    members: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = expand_table(table)
        if not rows:
            continue
        headers = [normalize_text(cell.get_text(" ", strip=True)) for cell in rows[0]]
        for cells in rows[1:]:
            values = [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]
            if not any(values):
                continue
            member = parse_tokyo_ward_table_row(config, headers, cells, values)
            if member:
                members.append(member)
    return root_payload(config, members)


def parse_tokyo_ward_table_row(config: dict[str, Any], headers: list[str], cells: list[Tag], values: list[str]) -> dict[str, Any] | None:
    cid = config["council_id"]
    kind = config["table_kind"]
    district = config["district"]
    if kind == "itabashi":
        if len(values) < 2 or "議員氏名" in values[0] or not values[0]:
            return None
        name, kana = split_name_kana(values[0])
        link = cells[0].find("a", href=True)
        return make_member(
            council_id=cid,
            name=name,
            kana=kana,
            district=district,
            faction=values[1],
            positions=positions_from_text(values[2] if len(values) > 2 else None),
            profile_url=urljoin(config["source_url"], link["href"]) if link else None,
        )
    if kind == "nerima":
        if len(values) < 3 or values[0] == "氏 名" or values[0] == "電 話":
            return None
        link = cells[0].find("a", href=True)
        committees = []
        for value in values[4:]:
            committees.extend(committee_tokens(value))
        return make_member(
            council_id=cid,
            name=values[0],
            kana=values[1],
            district=district,
            faction=values[2],
            committees=committees,
            positions=positions_from_text(" ".join(values[4:])),
            profile_url=urljoin(config["source_url"], link["href"]) if link else None,
        )
    if kind == "toshima":
        if len(values) < 6 or values[1] == "氏名" or not values[1] or values[1] == "欠員":
            return None
        name, kana = split_name_kana(values[1])
        link = cells[1].find("a", href=True)
        committee_text = values[5]
        return make_member(
            council_id=cid,
            name=name,
            kana=kana,
            district=district,
            faction=values[4],
            committees=committee_tokens(committee_text),
            positions=positions_from_text(committee_text),
            profile_url=urljoin(config["source_url"], link["href"]) if link else None,
        )
    return None


def parse_setagaya_ward(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    members: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for cell in soup.find_all("td"):
        text = normalize_text(cell.get_text(" ", strip=True))
        match = re.search(r"(?P<name>[^［\[(（]+?)[（(](?P<kana>[^）)]+)[）)]\s*[［\[](?P<faction>[^］\]]+)[］\]]", text)
        if not match:
            continue
        name = clean_member_name(match.group("name"))
        kana = compact_kana_text(match.group("kana"))
        key = (compact_name(name), kana)
        if key in seen:
            continue
        seen.add(key)
        member = make_member(
            council_id=config["council_id"],
            name=name,
            kana=kana,
            district=config["district"],
            faction=match.group("faction"),
        )
        if member:
            members.append(member)
    return root_payload(config, members)


def parse_chiyoda_ward(scraper: MunicipalOfficialMultiviewScraper, config: dict[str, Any]) -> dict[str, Any]:
    soup = scraper.fetch_soup(config["source_url"])
    text = normalize_text((soup.find("main") or soup.find("body") or soup).get_text(" ", strip=True))
    if "議員紹介" in text:
        text = text.split("議員紹介", 1)[1]
    text = text.split("ページの 先頭へ", 1)[0]
    members: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for match in re.finditer(r"(?:^|\s)([0-9０-９]{1,2})\s+(.+?)(?=\s+[0-9０-９]{1,2}\s+|$)", text):
        name = clean_member_name(match.group(2))
        if not name or any(word in name for word in ("定数", "現員", "議員", "紹介", "連絡先", "お問い合わせ")):
            continue
        if len(name) > 12:
            continue
        compact = compact_name(name)
        if compact in seen_names:
            continue
        seen_names.add(compact)
        member = make_member(council_id=config["council_id"], name=name, district=config["district"])
        if member:
            members.append(member)
    return root_payload(config, members)


PARSERS: dict[str, Callable[[MunicipalOfficialMultiviewScraper, dict[str, Any]], dict[str, Any]]] = {
    "sapporo": parse_sapporo,
    "simple_table": parse_simple_table,
    "fukuoka": parse_fukuoka,
    "saitama": parse_saitama,
    "yokohama": parse_yokohama,
    "sendai": parse_sendai,
    "kawasaki": parse_kawasaki,
    "sagamihara": parse_sagamihara,
    "niigata": parse_niigata,
    "osaka": parse_osaka,
    "hamamatsu": parse_hamamatsu,
    "kobe": parse_kobe,
    "okayama": parse_okayama,
    "kitakyushu": parse_kitakyushu,
    "tokyo_ward_links": parse_tokyo_ward_links,
    "tokyo_ward_table": parse_tokyo_ward_table,
    "setagaya_ward": parse_setagaya_ward,
    "chiyoda_ward": parse_chiyoda_ward,
}

CITY_CONFIGS: dict[str, dict[str, Any]] = {
    "sapporo-city": {"council_id": "sapporo-city", "name": "札幌市議会", "parser": "sapporo", "source_url": "https://www.city.sapporo.jp/gikai/meibo/meibo-ku.html", "teisu": 68, "source_basis_date": "公式基準日記載なし"},
    "sendai-city": {"council_id": "sendai-city", "name": "仙台市議会", "parser": "sendai", "source_url": "https://www.gikai.city.sendai.jp/list/district/index.html", "party_index_url": "https://www.gikai.city.sendai.jp/list/parties/index.html", "teisu": 55, "district_urls": {"青葉区": "https://www.gikai.city.sendai.jp/list/district/aoba/index.html", "宮城野区": "https://www.gikai.city.sendai.jp/list/district/miyagino/index.html", "若林区": "https://www.gikai.city.sendai.jp/list/district/wakabayashi/index.html", "太白区": "https://www.gikai.city.sendai.jp/list/district/taihaku/index.html", "泉区": "https://www.gikai.city.sendai.jp/list/district/izumi/index.html"}},
    "saitama-city": {"council_id": "saitama-city", "name": "さいたま市議会", "parser": "saitama", "source_url": "https://www.city.saitama.lg.jp/gikai/001/002/002/index.html", "teisu": 59, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員59人を件数検算アンカーとして使用"]},
    "chiba-city": {"council_id": "chiba-city", "name": "千葉市議会", "parser": "simple_table", "table_kind": "chiba", "source_url": "https://www.city.chiba.jp/shigikai/gojuon.html", "teisu": 50},
    "yokohama-city": {"council_id": "yokohama-city", "name": "横浜市会", "parser": "yokohama", "source_url": "https://www.city.yokohama.lg.jp/shikai/giin/50on.html", "teisu": 86},
    "kawasaki-city": {"council_id": "kawasaki-city", "name": "川崎市議会", "parser": "kawasaki", "source_url": "https://www.city.kawasaki.jp/shisei/category/40-3-4-0-0-0-0-0-0-0.html", "teisu": 59, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員59人を件数検算アンカーとして使用"]},
    "sagamihara-city": {"council_id": "sagamihara-city", "name": "相模原市議会", "parser": "sagamihara", "source_url": "https://www.sagamihara-shigikai.jp/doc/2013122400014/", "teisu": 46, "vacancy_details": [{"district": "中央区", "ketsuin": 1, "source_url": "https://www.sagamihara-shigikai.jp/doc/2013120600058/"}], "anchor_source_url": "https://www.sagamihara-shigikai.jp/doc/2013120600058/"},
    "niigata-city": {"council_id": "niigata-city", "name": "新潟市議会", "parser": "niigata", "source_url": "https://www.city.niigata.lg.jp/shigikai/index_meibo/meibo_01kubetsu.html", "teisu": 50},
    "shizuoka-city": {"council_id": "shizuoka-city", "name": "静岡市議会", "parser": "simple_table", "table_kind": "shizuoka", "source_url": "https://www.city.shizuoka.lg.jp/gikai/s900078.html", "teisu": 48},
    "hamamatsu-city": {"council_id": "hamamatsu-city", "name": "浜松市議会", "parser": "hamamatsu", "source_url": "https://www.city.hamamatsu.shizuoka.jp/gikai/iinkai/meibo50.html", "teisu": 44, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員44人を件数検算アンカーとして使用"]},
    "nagoya-city": {"council_id": "nagoya-city", "name": "名古屋市会", "parser": "simple_table", "table_kind": "nagoya", "source_url": "https://www.city.nagoya.jp/shikai/about/1030778/1030800.html", "teisu": 68},
    "kyoto-city": {"council_id": "kyoto-city", "name": "京都市会", "parser": "simple_table", "table_kind": "kyoto", "source_url": "https://www2.city.kyoto.lg.jp/shikai/meibo/gojuon.html", "teisu": 67},
    "osaka-city": {"council_id": "osaka-city", "name": "大阪市会", "parser": "osaka", "source_url": "https://www.city.osaka.lg.jp/shikai/page/0000310422.html", "teisu": 81},
    "sakai-city": {"council_id": "sakai-city", "name": "堺市議会", "parser": "simple_table", "table_kind": "sakai", "source_url": "https://www.city.sakai.lg.jp/shigikai/meibo/50on.html", "teisu": 48, "vacancy_details": [{"district": "欠員区未特定", "ketsuin": 1, "source_url": "https://www.city.sakai.lg.jp/shigikai/meibo/50on.html"}], "notes": ["公式50音表に定数48人と掲載がある一方、掲載行は47人。欠員区は同表から特定できないため未特定として記録"]},
    "kobe-city": {"council_id": "kobe-city", "name": "神戸市会", "parser": "kobe", "source_url": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/index.html", "teisu": 65, "district_urls": {"東灘区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/higashinada.html", "灘区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/nada.html", "中央区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/chuou.html", "兵庫区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/hyogo.html", "北区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/kita.html", "長田区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/nagata.html", "須磨区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/suma.html", "垂水区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/tarumi.html", "西区": "https://www.city.kobe.lg.jp/a71064/shise/municipal/giinnmeibo/sennkyoku/nishi.html"}},
    "okayama-city": {"council_id": "okayama-city", "name": "岡山市議会", "parser": "okayama", "source_url": "https://www.city.okayama.jp/gikai/0000015787.html", "teisu": 46},
    "hiroshima-city": {"council_id": "hiroshima-city", "name": "広島市議会", "parser": "simple_table", "table_kind": "hiroshima", "source_url": "https://www.city.hiroshima.lg.jp/gikai/giin-shoukai/1014892/index.html", "teisu": 51, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員51人を件数検算アンカーとして使用"]},
    "kitakyushu-city": {"council_id": "kitakyushu-city", "name": "北九州市議会", "parser": "kitakyushu", "source_url": "https://www.city.kitakyushu.lg.jp/sigikai/menu11_0002.html", "district_index_url": "https://www.city.kitakyushu.lg.jp/sigikai/menu11_0003.html", "teisu": 57},
    "fukuoka-city": {"council_id": "fukuoka-city", "name": "福岡市議会", "parser": "fukuoka", "source_url": "https://gikai.city.fukuoka.lg.jp/member/alphabet", "teisu": 62, "vacancy_details": [{"district": "早良区", "ketsuin": 1, "source_url": "https://gikai.city.fukuoka.lg.jp/member"}, {"district": "西区", "ketsuin": 1, "source_url": "https://gikai.city.fukuoka.lg.jp/member"}]},
    "kumamoto-city": {"council_id": "kumamoto-city", "name": "熊本市議会", "parser": "simple_table", "table_kind": "kumamoto", "source_url": "https://kumamoto-shigikai.jp/namelist/pub/list50.aspx?c_id=3", "teisu": 47, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員47人を件数検算アンカーとして使用"]},
    "minato-ward": {"council_id": "minato-ward", "name": "港区議会", "parser": "tokyo_ward_links", "source_url": "https://www.gikai.city.minato.tokyo.jp/0000000684.html", "member_href_re": r"/00000025\d+\.html$", "district": "港区", "teisu": 34, "source_basis_date": "公式名簿 定数34人・欠員2人", "vacancy_details": [{"district": "港区", "ketsuin": 2, "source_url": "https://www.gikai.city.minato.tokyo.jp/0000000684.html"}]},
    "koto-ward": {"council_id": "koto-ward", "name": "江東区議会", "parser": "tokyo_ward_links", "source_url": "https://www.city.koto.lg.jp/kuse/kugikai/shokai/gisekijun/index.html", "member_href_re": r"/gisekijun/\d+\.html$", "district": "江東区", "teisu": 39, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員39人を件数検算アンカーとして使用"]},
    "shinagawa-ward": {"council_id": "shinagawa-ward", "name": "品川区議会", "parser": "tokyo_ward_links", "source_url": "https://gikai.city.shinagawa.tokyo.jp/profile/50on", "member_href_re": r"/councillors/", "district": "品川区", "teisu": 37, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員37人を件数検算アンカーとして使用"]},
    "setagaya-ward": {"council_id": "setagaya-ward", "name": "世田谷区議会", "parser": "setagaya_ward", "source_url": "https://www.city.setagaya.lg.jp/02030/9461.html", "district": "世田谷区", "teisu": 50, "source_basis_date": "令和8年6月15日現在 / 定数50人・現員50人"},
    "shibuya-ward": {"council_id": "shibuya-ward", "name": "渋谷区議会", "parser": "tokyo_ward_links", "source_url": "https://shibukugi.tokyo/giin/2023012400017/", "member_href_re": r"/giin/profile/", "district": "渋谷区", "teisu": 32, "source_basis_date": "令和8年1月27日更新 / 掲載32人", "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員32人を件数検算アンカーとして使用"]},
    "nakano-ward": {"council_id": "nakano-ward", "name": "中野区議会", "parser": "tokyo_ward_links", "source_url": "https://kugikai-nakano.jp/giin_list.html", "member_href_re": r"giin_detail\.html\?giin_id=", "district": "中野区", "teisu": 41, "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員41人を件数検算アンカーとして使用"]},
    "suginami-ward": {"council_id": "suginami-ward", "name": "杉並区議会", "parser": "tokyo_ward_links", "source_url": "https://www.city.suginami.tokyo.jp/s117/kugikai/18847.html", "member_href_re": r"/kugikai/s117/4\d+\.html$", "exclude_labels": ["会派別一覧", "議席配置図", "常任・特別委員会の仕事と名簿"], "district": "杉並区", "teisu": 46, "source_basis_date": "令和8年5月13日更新 / 掲載46人", "anchor_type": "official_roster_count", "notes": ["公式ページ内に定数・欠員表示がないため、掲載現員46人を件数検算アンカーとして使用"]},
    "itabashi-ward": {"council_id": "itabashi-ward", "name": "板橋区議会", "parser": "tokyo_ward_table", "table_kind": "itabashi", "source_url": "https://www.city.itabashi.tokyo.jp/kugikai/giin/1010916.html", "district": "板橋区", "teisu": 46, "source_basis_date": "公式名簿 定数46人・現員44人", "vacancy_details": [{"district": "板橋区", "ketsuin": 2, "source_url": "https://www.city.itabashi.tokyo.jp/kugikai/giin/1010916.html"}]},
    "nerima-ward": {"council_id": "nerima-ward", "name": "練馬区議会", "parser": "tokyo_ward_table", "table_kind": "nerima", "source_url": "https://www.city.nerima.tokyo.jp/gikai/giin/20ichiran.html", "district": "練馬区", "teisu": 50, "source_basis_date": "令和8年5月26日現在 / 定数50人・在職議員50人"},
    "chiyoda-ward": {"council_id": "chiyoda-ward", "name": "千代田区議会", "parser": "chiyoda_ward", "source_url": "https://gikai-chiyoda-tokyo.jp/about/giin/index.html", "district": "千代田区", "teisu": 25, "source_basis_date": "公式名簿 定数25人・現員22人", "vacancy_details": [{"district": "千代田区", "ketsuin": 3, "source_url": "https://gikai-chiyoda-tokyo.jp/about/giin/index.html"}]},
    "toshima-ward": {"council_id": "toshima-ward", "name": "豊島区議会", "parser": "tokyo_ward_table", "table_kind": "toshima", "source_url": "https://www.city.toshima.lg.jp/366/kuse/gikai/ginichiran/mebo/2404241622.html", "district": "豊島区", "teisu": 36, "source_basis_date": "公式名簿 掲載34人・欠員2人", "vacancy_details": [{"district": "豊島区", "ketsuin": 2, "source_url": "https://www.city.toshima.lg.jp/366/kuse/gikai/ginichiran/mebo/2404241622.html"}]},
}


def run_city(city_id: str) -> int:
    scraper = MunicipalOfficialMultiviewScraper()
    payload = scraper.scrape_members(city_id)
    scraper.save_json(out_path(city_id), payload)
    print(f"{city_id}: {len(payload['members'])} members / teisu {payload['teisu']} / ketsuin {payload['ketsuin']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: municipal_official_multiview_roster.py <city-id>", file=sys.stderr)
        return 2
    return run_city(args[0])


if __name__ == "__main__":
    raise SystemExit(main())
