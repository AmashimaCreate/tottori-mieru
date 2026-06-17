"""kitakyushu-city municipal council roster builder."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.municipal_official_multiview_roster import run_city  # noqa: E402


def main() -> int:
    return run_city("kitakyushu-city")


if __name__ == "__main__":
    raise SystemExit(main())
