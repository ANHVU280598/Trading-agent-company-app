#!/usr/bin/env python3
"""Download/cache Model v5 price history → data/history/{TICKER}.csv."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.history_cache import HISTORY_DIR, fetch_universe  # noqa: E402
from core.universe import assert_universe_frozen, universe_tickers  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2014-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    info = assert_universe_frozen()
    tickers = universe_tickers()
    print(f"universe v{info['version']} hash={info['hash']} n={len(tickers)}")
    report = fetch_universe(
        tickers,
        start=args.start,
        end=args.end,
        directory=HISTORY_DIR,
        max_workers=args.workers,
        force=args.force,
    )
    ok = sum(1 for m in report["tickers"].values() if m.get("quality", {}).get("rows", 0) > 0)
    print(json.dumps({"cached_or_fetched": ok, "of": len(tickers)}, indent=2))
    return 0 if ok == len(tickers) else 1


if __name__ == "__main__":
    raise SystemExit(main())
