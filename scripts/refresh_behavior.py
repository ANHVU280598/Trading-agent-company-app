#!/usr/bin/env python3
"""Refresh Model v4 behavior table → data/behavior.csv + SQLite.

Sources: Yahoo ^VIX, CBOE totalpc.csv, AAII sentiment.xls (Wayback fallback).
Does NOT scrape CNN Fear & Greed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core import db  # noqa: E402
from core.behavior_data import (  # noqa: E402
    BEHAVIOR_COUNTS_JSON,
    BEHAVIOR_CSV,
    build_behavior_table,
    save_behavior_csv,
    save_counts,
)
from core.config import DB_PATH  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--csv", type=Path, default=BEHAVIOR_CSV)
    parser.add_argument("--counts", type=Path, default=BEHAVIOR_COUNTS_JSON)
    args = parser.parse_args()

    print(f"building behavior {args.start} .. {args.end or 'today'}")
    frame, meta = build_behavior_table(args.start, args.end)

    csv_path = save_behavior_csv(frame, args.csv)
    counts_path = save_counts(meta, args.counts)
    db.init_db(args.db)
    n = db.replace_behavior(frame, args.db)

    print(f"wrote {csv_path} rows={len(frame)}")
    print(f"wrote {counts_path}")
    print(f"sqlite behavior rows={n} db={args.db}")
    print(json.dumps({k: meta.get(k) for k in ("vix", "putcall", "aaii", "rows")}, indent=2))
    return 0 if meta.get("vix", {}).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
