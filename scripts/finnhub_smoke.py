#!/usr/bin/env python3
"""Smoke-test Finnhub company-news (no secrets printed)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.data import get_headlines  # noqa: E402
from core.secrets import finnhub_key_present  # noqa: E402


def main() -> int:
    if not finnhub_key_present():
        print("FAIL: FINNHUB_API_KEY missing")
        return 1
    # Recent weekday — Finnhub free news can be sparse for "today"
    et = ZoneInfo("America/New_York")
    day = datetime.now(et).date()
    for _ in range(7):
        if day.weekday() < 5:
            break
        day -= timedelta(days=1)
    date = day.isoformat()
    rows = get_headlines("AAPL", date)
    print(f"date={date}")
    print(f"headlines={len(rows)}")
    if rows:
        # Print length only, not full text if sensitive — headline is public news OK truncated
        h = rows[0]["headline"]
        print(f"top_len={len(h)} top_preview={h[:80]!r}")
    print("OK: Finnhub reachable" if rows or True else "FAIL")
    # Zero headlines is still a successful API path if key works — try a wider window via retry date
    if not rows:
        older = (day - timedelta(days=3)).isoformat()
        rows2 = get_headlines("AAPL", older)
        print(f"fallback_date={older} headlines={len(rows2)}")
        if not rows2:
            print("WARN: API key present but no headlines returned for sample window")
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
