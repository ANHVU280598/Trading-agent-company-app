#!/usr/bin/env python3
"""Refresh Model v3 events calendar → data/events.csv + SQLite events table.

Run monthly (or on demand). Auditable CSV is committed; app.db stays gitignored.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core import db  # noqa: E402
from core.config import DB_PATH, DEFAULT_WATCHLIST  # noqa: E402
from core.events_calendar import (  # noqa: E402
    EVENTS_COUNTS_JSON,
    EVENTS_CSV,
    build_all_events,
    save_counts,
    save_events_csv,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2027-12-31")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument(
        "--csv",
        type=Path,
        default=EVENTS_CSV,
        help="Committed CSV path (default data/events.csv)",
    )
    parser.add_argument(
        "--counts",
        type=Path,
        default=EVENTS_COUNTS_JSON,
        help="Committed counts JSON for Anh review",
    )
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    print(f"building events {start} .. {end} tickers={DEFAULT_WATCHLIST}")
    frame, meta = build_all_events(start, end, DEFAULT_WATCHLIST)

    csv_path = save_events_csv(frame, args.csv)
    counts_path = save_counts(meta, args.counts)
    db.init_db(args.db)
    n = db.replace_events(frame, args.db)

    print(f"wrote {csv_path} rows={len(frame)}")
    print(f"wrote {counts_path}")
    print(f"sqlite events rows={n} db={args.db}")
    print(json.dumps(meta.get("counts"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
