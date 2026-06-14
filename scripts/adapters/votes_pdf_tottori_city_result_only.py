#!/usr/bin/env python3
"""Build Tottori City Council result-only vote data from official PDFs.

Tottori City publishes member-level vote matrices, but the PDF structure is
mixed across sessions. This adapter intentionally records only bill-level
outcomes that can be read from the official PDF: bill number/title, date,
result, and source URL. Member votes are left null.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pdfplumber


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.json_output import write_json_if_entity_changed  # noqa: E402


DATA_DIR = REPO_ROOT / "docs" / "data"
LISTING_URL = "https://www.city.tottori.lg.jp/site/shigikai/6332.html"
COUNCIL_ID = "tottori-city"
OUT_PATH = DATA_DIR / COUNCIL_ID / "votes.json"
USER_AGENT = "Mozilla/5.0 (compatible; tottori-mieru/1.0)"
SLEEP_SECONDS = 2.0

SESSION_RE = re.compile(
    r"(?P<label>(?:令和|平成)[0-9０-９元]+年(?:第[0-9０-９]+回)?[0-9０-９]*月?(?:定例会|臨時会))"
)
DATE_PATTERN = r"(?:令和|平成)[0-9０-９元]+年[0-9０-９]+月[0-9０-９]+日"
DATE_RE = re.compile(f"({DATE_PATTERN})")
ROW_RE = re.compile(r"^\s*(?P<number>[0-9０-９]+)\s+(?P<rest>.+?)\s+" + DATE_RE.pattern)
RESULT_WORDS = (
    "原案可決",
    "原案否決",
    "可決",
    "否決",
    "承認",
    "不承認",
    "認定",
    "不認定",
    "同意",
    "不同意",
    "採択",
    "不採択",
    "趣旨採択",
    "継続審査",
    "研究留保",
)
NOISE_TERMS = (
    "委員会",
    "全会一致",
    "賛成多数",
    "賛成少数",
    "討論",
    "採決",
    "議決年月日",
    "議決結果",
    "審査結果",
)


def normalize_digits(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_digits(value)).strip()


def parse_count(value: str) -> int:
    value = normalize_digits(value)
    if value == "元":
        return 1
    return int(value)


def default_start_date(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    return dt.date(today.year - 2, today.month, 1)


def parse_japanese_date(value: str) -> str:
    match = re.fullmatch(r"(令和|平成)([0-9０-９元]+)年([0-9０-９]+)月([0-9０-９]+)日", value)
    if not match:
        raise ValueError(f"unsupported date: {value}")
    era, year_raw, month_raw, day_raw = match.groups()
    era_base = 2018 if era == "令和" else 1988
    year = era_base + parse_count(year_raw)
    return dt.date(year, parse_count(month_raw), parse_count(day_raw)).isoformat()


def parse_session_month(label: str) -> dt.date | None:
    match = re.search(r"(令和|平成)([0-9０-９元]+)年(?:第[0-9０-９]+回)?([0-9０-９]+)?月?", label)
    if not match:
        return None
    era, year_raw, month_raw = match.groups()
    era_base = 2018 if era == "令和" else 1988
    year = era_base + parse_count(year_raw)
    month = parse_count(month_raw) if month_raw else 1
    return dt.date(year, month, 1)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def discover_sessions(start: dt.date, end: dt.date) -> list[dict[str, str]]:
    body = fetch_text(LISTING_URL)
    anchor_re = re.compile(
        r'<a\b[^>]*href="(?P<href>[^"]+\.pdf)"[^>]*>(?P<label>[^<]*(?:定例会|臨時会)[^<]*議決結果[^<]*)</a>',
        re.IGNORECASE,
    )
    sessions: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in anchor_re.finditer(body):
        raw_label = normalize_spaces(html.unescape(match.group("label")))
        session_match = SESSION_RE.search(raw_label)
        if not session_match:
            continue
        session = session_match.group("label")
        session_month = parse_session_month(session)
        if session_month is None or session_month < start or session_month > end:
            continue
        source_url = urllib.parse.urljoin(LISTING_URL, html.unescape(match.group("href")))
        if source_url in seen:
            continue
        seen.add(source_url)
        sessions.append(
            {
                "session": session,
                "session_month": session_month.isoformat(),
                "source_url": source_url,
            }
        )
    return sorted(sessions, key=lambda item: item["session_month"], reverse=True)


def download_pdf(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        dest.write_bytes(response.read())


def pdftotext(pdf_path: Path) -> str:
    if shutil.which("pdftotext") is None:
        raise RuntimeError("pdftotext is not available")
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout


def parse_pdf_words(pdf_path: Path, session: str, source_url: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page_count = 0
    date_words_seen = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=False,
            )
            if not words:
                continue

            date_words = [
                word for word in words
                if DATE_RE.fullmatch(normalize_digits(word["text"]))
            ]
            date_words_seen += len(date_words)
            for date_word in date_words:
                row_top = date_word["top"]
                number_word = nearest_word(
                    words,
                    row_top=row_top,
                    x_min=50,
                    x_max=140,
                    pattern=r"^[0-9０-９]+$",
                )
                if not number_word:
                    continue
                result = nearest_result(words, row_top)
                if not result or result == "報告":
                    continue
                title = extract_title_from_words(words, row_top)
                if not title:
                    title = "議案名不明"
                title = clean_bill_title(title)

                number = normalize_digits(number_word["text"])
                bill_no = f"議案第{number}号"
                date_value = parse_japanese_date(normalize_digits(date_word["text"]))
                records.append(
                    {
                        "id": build_vote_id(session, bill_no, date_value, result, title),
                        "council_id": COUNCIL_ID,
                        "session": session,
                        "category": None,
                        "bill_no": bill_no,
                        "bill_title": title,
                        "date": date_value,
                        "result": result,
                        "granularity": "result_only",
                        "votes_by_member": None,
                        "votes_by_faction": None,
                        "source_url": source_url,
                        "source_row_index": len(records) + 1,
                        "source_page": page_index,
                    }
                )

    has_extractable_text = date_words_seen > 0
    diagnostics = {
        "accepted": has_extractable_text and len(records) > 0,
        "is_text_pdf": has_extractable_text,
        "page_count": page_count,
        "date_rows_seen": date_words_seen,
        "checks": {
            "parsed_count": len(records),
            "date_rows_seen": date_words_seen,
            "has_extractable_text": has_extractable_text,
            "extraction_method": "pdfplumber_words",
        },
    }
    return records, diagnostics


def nearest_word(
    words: list[dict[str, Any]],
    row_top: float,
    x_min: float,
    x_max: float,
    pattern: str,
    y_tolerance: float = 5.5,
) -> dict[str, Any] | None:
    matcher = re.compile(pattern)
    candidates = [
        word for word in words
        if x_min <= word["x0"] <= x_max
        and abs(word["top"] - row_top) <= y_tolerance
        and matcher.match(normalize_digits(word["text"]))
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda word: abs(word["top"] - row_top))


def nearest_result(words: list[dict[str, Any]], row_top: float) -> str | None:
    candidates = [
        normalize_digits(word["text"])
        for word in words
        if word["x0"] >= 1056
        and abs(word["top"] - row_top) <= 9
        and normalize_digits(word["text"]) in RESULT_WORDS
    ]
    if candidates:
        return candidates[0]

    # Some PDFs place the result just left of the final result column. Use it
    # only as a fallback, still constrained to the same row band.
    fallback = [
        normalize_digits(word["text"])
        for word in words
        if 560 <= word["x0"] < 680
        and abs(word["top"] - row_top) <= 9
        and normalize_digits(word["text"]) in RESULT_WORDS
    ]
    return fallback[0] if fallback else None


def extract_title_from_words(words: list[dict[str, Any]], row_top: float) -> str:
    title_words = [
        word for word in words
        if 78 <= word["x0"] < 270
        and row_top - 8 <= word["top"] <= row_top + 14
    ]
    title_words.sort(key=lambda word: (word["top"], word["x0"]))
    fragments: list[str] = []
    for word in title_words:
        text = normalize_spaces(word["text"])
        if not text:
            continue
        if text.startswith("＜") and text.endswith("＞"):
            continue
        if any(term in text for term in NOISE_TERMS):
            continue
        if re.fullmatch(r"[()（）0-9０-９件\s]+", text):
            continue
        fragments.append(text)
    return normalize_spaces("".join(fragments))


def clean_bill_title(title: str) -> str:
    title = normalize_spaces(title)
    title = title.replace("（第1", "（第1号）")
    title = title.replace("（第2", "（第2号）")
    title = title.replace("（第3", "（第3号）")
    title = title.replace("（第4", "（第4号）")
    title = title.replace("（第5", "（第5号）")
    title = re.sub(r"令和[0-9]+年度補正予算", "", title)
    title = re.sub(r"契約金額[:：][^工財条専人市鳥]*", "", title)
    title = re.sub(r"取得金額[:：][^財条専人市鳥]*", "", title)
    marker = "について"
    if marker in title:
        title = title[: title.find(marker) + len(marker)]
    title = re.sub(r"議決を得るもの.*$", "", title)
    title = title.replace("予算号)", "予算(号)")
    title = title.replace("号）号)", "号）")
    title = title.replace("号)号)", "号)")
    title = title.replace("（第1号）号)", "（第1号）")
    title = title.replace("（第2号）号)", "（第2号）")
    title = title.replace("（第3号）号)", "（第3号）")
    title = title.replace("（第4号）号)", "（第4号）")
    title = title.replace("（第5号）号)", "（第5号）")
    return normalize_spaces(title) or "議案名不明"


def build_vote_id(session: str, bill_no: str, date_value: str, result: str, title: str = "") -> str:
    digest = hashlib.sha1(
        f"{session}|{bill_no}|{date_value}|{result}|{title}".encode("utf-8")
    ).hexdigest()[:10]
    slug = re.sub(r"[^0-9A-Za-z一-龥ぁ-んァ-ンー]+", "-", f"{session}-{bill_no}")
    slug = slug.strip("-")[:80]
    return f"{COUNCIL_ID}--{slug}-{digest}"


def title_fragment(line: str) -> str:
    fragment = normalize_spaces(line[13:48])
    if not fragment:
        return ""
    if re.fullmatch(r"[()（）0-9０-９件\s]+", fragment):
        return ""
    if any(term in fragment for term in NOISE_TERMS):
        return ""
    if re.search(r"^[〇○×議長無有\s]+$", fragment):
        return ""
    return fragment


def title_from_row(line: str) -> str:
    match = re.match(r"^\s*[0-9０-９]+\s{1,6}(.+?)\s{2,}", normalize_digits(line))
    if not match:
        return ""
    candidate = normalize_spaces(match.group(1))
    if DATE_RE.search(candidate):
        candidate = DATE_RE.split(candidate)[0]
    if any(term in candidate for term in NOISE_TERMS):
        return ""
    return candidate


def result_from_window(lines: list[str], index: int) -> str | None:
    window = lines[max(0, index - 2): min(len(lines), index + 3)]
    for line in window:
        for word in RESULT_WORDS:
            if word in line:
                return word
    return None


def parse_pdf_text(text: str, session: str, source_url: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lines = [line.replace("\f", "") for line in text.splitlines()]
    has_extractable_text = len(text.strip()) > 300 and bool(lines)
    records: list[dict[str, Any]] = []
    report_rows = 0

    for index, line in enumerate(lines):
        match = ROW_RE.search(line)
        if not match:
            continue
        date_raw = match.group(3)
        date_value = parse_japanese_date(date_raw)
        result = result_from_window(lines, index)
        if result is None:
            continue
        if result == "報告":
            report_rows += 1
            continue

        number = normalize_digits(match.group("number"))
        row_title = title_from_row(line)
        if row_title:
            title = row_title
        else:
            fragments: list[str] = []
            for candidate in lines[max(0, index - 3): min(len(lines), index + 3)]:
                if candidate is line:
                    continue
                fragment = title_fragment(candidate)
                if fragment:
                    fragments.append(fragment)
            title = normalize_spaces("".join(fragments))
        if not title:
            title = "議案名不明"

        bill_no = f"議案第{number}号"
        records.append(
            {
                "id": build_vote_id(session, bill_no, date_value, result, title),
                "council_id": COUNCIL_ID,
                "session": session,
                "category": None,
                "bill_no": bill_no,
                "bill_title": title,
                "date": date_value,
                "result": result,
                "granularity": "result_only",
                "votes_by_member": None,
                "votes_by_faction": None,
                "source_url": source_url,
                "source_row_index": len(records) + 1,
            }
        )

    diagnostics = {
        "accepted": has_extractable_text and len(records) > 0,
        "is_text_pdf": has_extractable_text,
        "text_characters": len(text),
        "report_rows_excluded": report_rows,
        "checks": {
            "parsed_count": len(records),
            "report_rows_excluded": report_rows,
            "has_extractable_text": has_extractable_text,
        },
    }
    return records, diagnostics


def build_payload(start: dt.date, end: dt.date) -> dict[str, Any]:
    sessions = discover_sessions(start, end)
    all_votes: list[dict[str, Any]] = []
    source_checks: list[dict[str, Any]] = []
    omitted_sessions: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="tottori-city-votes-") as tmpdir:
        tmp = Path(tmpdir)
        for i, session_info in enumerate(sessions, start=1):
            pdf_path = tmp / f"session_{i}.pdf"
            download_pdf(session_info["source_url"], pdf_path)
            time.sleep(SLEEP_SECONDS)
            votes, diagnostics = parse_pdf_words(
                pdf_path,
                session=session_info["session"],
                source_url=session_info["source_url"],
            )
            source_checks.append({**session_info, **diagnostics})
            if diagnostics["accepted"]:
                all_votes.extend(votes)
            else:
                omitted_sessions.append(
                    {
                        "session": session_info["session"],
                        "source_url": session_info["source_url"],
                        "reason": "テキスト抽出不可または議決結果行を検出できないため未収録",
                        "checks": diagnostics["checks"],
                    }
                )

    all_votes.sort(
        key=lambda item: (
            item["date"] or "",
            item["session"],
            item["bill_no"],
            item["id"],
        )
    )
    for i, vote in enumerate(all_votes, start=1):
        vote["source_row_index"] = i

    return {
        "council_id": COUNCIL_ID,
        "updated_at": dt.datetime.now(dt.UTC).isoformat(),
        "acquisition": "scraping",
        "granularity": "result_only",
        "source_url": LISTING_URL,
        "coverage": {
            "scope": "直近2年分の定例会・臨時会の議決結果PDF",
            "note": "議員別賛否PDFは会期により抽出可否が異なるため、このファイルでは議案ごとの議決結果のみを収録する。",
        },
        "source_checks": source_checks,
        "omitted_sessions": omitted_sessions,
        "votes": all_votes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=dt.date.fromisoformat, default=default_start_date())
    parser.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = build_payload(args.start, args.end)
    if not args.dry_run:
        write_json_if_entity_changed(args.output, payload)

    for check in payload["source_checks"]:
        summary = check["checks"]
        print(
            f"{check['session']}: parsed={summary['parsed_count']} "
            f"date_rows={summary.get('date_rows_seen', 0)} "
            f"text_pdf={check['is_text_pdf']} accepted={check['accepted']}"
        )
    if payload["omitted_sessions"]:
        print(f"{COUNCIL_ID}: omitted_sessions={len(payload['omitted_sessions'])}")
        for item in payload["omitted_sessions"]:
            print(f"- {item['session']}: {item['reason']}")
    print(
        f"{COUNCIL_ID}: sessions_seen={len(payload['source_checks'])}, "
        f"votes={len(payload['votes'])}, output={args.output}"
    )


if __name__ == "__main__":
    main()
