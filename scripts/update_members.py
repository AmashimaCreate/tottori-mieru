#!/usr/bin/env python3
"""Run all active council member builders with per-council failure isolation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

MEMBER_SCRIPTS = [
    ("hokkaido-pref", "scripts/councils/hokkaido_pref.py"),
    ("aomori-pref", "scripts/councils/aomori_pref.py"),
    ("iwate-pref", "scripts/councils/iwate_pref.py"),
    ("miyagi-pref", "scripts/councils/miyagi_pref.py"),
    ("akita-pref", "scripts/councils/akita_pref.py"),
    ("yamagata-pref", "scripts/councils/yamagata_pref.py"),
    ("fukushima-pref", "scripts/councils/fukushima_pref.py"),
    ("ibaraki-pref", "scripts/councils/ibaraki_pref.py"),
    ("tochigi-pref", "scripts/councils/tochigi_pref.py"),
    ("gunma-pref", "scripts/councils/gunma_pref.py"),
    ("saitama-pref", "scripts/councils/saitama_pref.py"),
    ("chiba-pref", "scripts/councils/chiba_pref.py"),
    ("tokyo-pref", "scripts/councils/tokyo_pref.py"),
    ("kanagawa-pref", "scripts/councils/kanagawa_pref.py"),
    ("niigata-pref", "scripts/councils/niigata_pref.py"),
    ("toyama-pref", "scripts/councils/toyama_pref.py"),
    ("ishikawa-pref", "scripts/councils/ishikawa_pref.py"),
    ("fukui-pref", "scripts/councils/fukui_pref.py"),
    ("yamanashi-pref", "scripts/councils/yamanashi_pref.py"),
    ("nagano-pref", "scripts/councils/nagano_pref.py"),
    ("gifu-pref", "scripts/councils/gifu_pref.py"),
    ("shizuoka-pref", "scripts/councils/shizuoka_pref.py"),
    ("aichi-pref", "scripts/councils/aichi_pref.py"),
    ("mie-pref", "scripts/councils/mie_pref.py"),
    ("shiga-pref", "scripts/councils/shiga_pref.py"),
    ("kyoto-pref", "scripts/councils/kyoto_pref.py"),
    ("osaka-pref", "scripts/councils/osaka_pref.py"),
    ("hyogo-pref", "scripts/councils/hyogo_pref.py"),
    ("nara-pref", "scripts/councils/nara_pref.py"),
    ("wakayama-pref", "scripts/councils/wakayama_pref.py"),
    ("tottori-pref", "scripts/councils/tottori_pref.py"),
    ("shimane-pref", "scripts/councils/shimane_pref.py"),
    ("okayama-pref", "scripts/councils/okayama_pref.py"),
    ("hiroshima-pref", "scripts/councils/hiroshima_pref.py"),
    ("yamaguchi-pref", "scripts/councils/yamaguchi_pref.py"),
    ("kumamoto-pref", "scripts/councils/kumamoto_pref.py"),
    ("fukuoka-pref", "scripts/councils/fukuoka_pref.py"),
    ("miyazaki-pref", "scripts/councils/miyazaki_pref.py"),
    ("kagoshima-pref", "scripts/councils/kagoshima_pref.py"),
    ("okinawa-pref", "scripts/councils/okinawa_pref.py"),
    ("saga-pref", "scripts/councils/saga_pref.py"),
    ("nagasaki-pref", "scripts/councils/nagasaki_pref.py"),
    ("oita-pref", "scripts/councils/oita_pref.py"),
    ("tokushima-pref", "scripts/councils/tokushima_pref.py"),
    ("kagawa-pref", "scripts/councils/kagawa_pref.py"),
    ("ehime-pref", "scripts/councils/ehime_pref.py"),
    ("kochi-pref", "scripts/councils/kochi_pref.py"),
    ("tottori-city", "scripts/councils/tottori_city.py"),
    ("yonago-city", "scripts/councils/yonago.py"),
    ("kurayoshi-city", "scripts/councils/kurayoshi.py"),
    ("sakaiminato-city", "scripts/councils/sakaiminato.py"),
]


def active_council_ids() -> set[str]:
    data = json.loads((REPO_ROOT / "councils.json").read_text(encoding="utf-8"))
    return {
        council["id"]
        for council in data.get("councils", [])
        if council.get("status") == "active"
    }


def run_script(council_id: str, script: str) -> dict[str, object]:
    print(f"== {council_id}: {script} ==", flush=True)
    result = subprocess.run(
        [sys.executable, script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return {
        "council_id": council_id,
        "script": script,
        "returncode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    active = active_council_ids()
    configured = {council_id for council_id, _ in MEMBER_SCRIPTS}
    missing = sorted(active - configured)
    if missing:
        print(f"Active councils missing from update_members.py: {missing}", file=sys.stderr)

    results = [
        run_script(council_id, script)
        for council_id, script in MEMBER_SCRIPTS
        if council_id in active
    ]
    failures = [item for item in results if not item["ok"]]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "active_count": len(active),
        "configured_count": len(configured),
        "missing_active_councils": missing,
        "results": results,
        "failures": failures,
    }
    if args.report:
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if missing or failures:
        print("Member update finished with failures:", file=sys.stderr)
        for item in failures:
            print(
                f"- {item['council_id']}: {item['script']} exited {item['returncode']}",
                file=sys.stderr,
            )
        return 1
    print(f"Member update OK: {len(results)} active councils")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
