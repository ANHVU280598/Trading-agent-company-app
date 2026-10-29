#!/usr/bin/env python3
"""Phase 5 review checklist status (ops harness — no build / no Live unlock).

Prints Muse gate numbers against current paper SQLite/JSON. Verdict is always
informational; Live stays locked until Muse+Tuan say otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core import db  # noqa: E402
from core.config import DB_PATH, ROOT as APP_ROOT  # noqa: E402


def _weeks_between(a: str, b: str) -> float:
    d0 = datetime.strptime(a[:10], "%Y-%m-%d")
    d1 = datetime.strptime(b[:10], "%Y-%m-%d")
    return (d1 - d0).days / 7.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument(
        "--out",
        type=Path,
        default=APP_ROOT / "data" / "paper_phase5_status.json",
    )
    args = parser.parse_args()

    db.init_db(args.db)
    trades = db.read_trades(args.db)
    hist = db.read_portfolio_history(args.db)

    closed = trades[trades["status"] == "Closed"] if not trades.empty else trades
    n_closed = int(len(closed))
    start = str(hist.iloc[0]["date"]) if not hist.empty else None
    end = str(hist.iloc[-1]["date"]) if not hist.empty else None
    weeks = _weeks_between(start, end) if start and end else 0.0

    expectancy = None
    if n_closed:
        wins = closed[closed["realized_pnl"].fillna(0) > 0]
        losses = closed[closed["realized_pnl"].fillna(0) <= 0]
        wr = len(wins) / n_closed
        lr = 1.0 - wr
        avg_win = float(wins["realized_pnl"].mean()) if len(wins) else 0.0
        avg_loss = float((-losses["realized_pnl"]).mean()) if len(losses) else 0.0
        # Muse: win rate × average win − loss rate × average loss
        expectancy = wr * avg_win - lr * avg_loss

    agent_dd = None
    bench_dd = None
    if not hist.empty:
        agent = hist["value"].astype(float)
        bench = hist["benchmark_value"].astype(float)
        agent_dd = float((agent / agent.cummax() - 1.0).min())
        bench_dd = float((bench / bench.cummax() - 1.0).min())

    checks = {
        "closed_trades_ge_30": n_closed >= 30,
        "weeks_ge_6": weeks >= 6.0,
        "expectancy_positive": (expectancy is not None and expectancy > 0),
        "dd_not_worse_than_bench": (
            agent_dd is not None
            and bench_dd is not None
            and agent_dd >= bench_dd  # less negative or equal
        ),
    }
    all_ok = all(checks.values())
    verdict = "Ready for Muse/Tuan Phase 5 review numbers" if all_ok else "Not proven yet"

    report = {
        "as_of": end,
        "paper_start": start,
        "weeks_running": round(weeks, 2),
        "closed_trades": n_closed,
        "expectancy_after_costs_proxy": expectancy,
        "agent_max_drawdown": agent_dd,
        "benchmark_max_drawdown": bench_dd,
        "checks": checks,
        "verdict": verdict,
        "note": "Informational only. Live trading stays locked. Local paper log is uncosted.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
