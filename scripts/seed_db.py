#!/usr/bin/env python3
"""Import fixtures/paper_state.json + paper_trades.csv into data/app.db once.

After seeding, SQLite is the app read source. JSON/CSV remain agent files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import DB_PATH, DEFAULT_WATCHLIST  # noqa: E402
from core import db  # noqa: E402


def seed(
    state_path: Path,
    trades_path: Path,
    db_path: Path = DB_PATH,
    results_path: Path | None = None,
) -> dict[str, float]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    trades = pd.read_csv(trades_path)
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        conn.execute("DELETE FROM portfolio_history")
        conn.execute("DELETE FROM positions")
        conn.execute("DELETE FROM signals")
        conn.execute("DELETE FROM trades")
        conn.execute("DELETE FROM model_runs")
        conn.execute("DELETE FROM signal_grades")

        for row in state.get("portfolio_history", []):
            conn.execute(
                "INSERT INTO portfolio_history(date, value, benchmark_value, cash, drawdown) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    row["date"],
                    row["value"],
                    row["benchmark_value"],
                    row["cash"],
                    row["drawdown"],
                ),
            )
        for row in state.get("positions", []):
            conn.execute(
                "INSERT INTO positions(ticker, shares, avg_cost) VALUES (?, ?, ?)",
                (row["ticker"], row["shares"], row["avg_cost"]),
            )
        for row in state.get("signals", []):
            conn.execute(
                "INSERT INTO signals(date, ticker, signal, buy_p, hold_p, sell_p, price, "
                "rsi14, drawdown63, sentiment, headline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["date"],
                    row["ticker"],
                    row["signal"],
                    row["buy_p"],
                    row["hold_p"],
                    row["sell_p"],
                    row["price"],
                    row["rsi14"],
                    row["drawdown63"],
                    row.get("sentiment"),
                    row.get("headline"),
                ),
            )
        for _, row in trades.iterrows():
            pnl = row["realized_pnl"]
            if pd.isna(pnl):
                pnl = None
            conn.execute(
                "INSERT INTO trades(id, date, ticker, action, shares, price, confidence, "
                "status, realized_pnl) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    int(row["id"]),
                    row["date"],
                    row["ticker"],
                    row["action"],
                    float(row["shares"]),
                    float(row["price"]),
                    float(row["confidence"]),
                    row["status"],
                    pnl,
                ),
            )

        # Default settings if empty
        existing = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        if existing == 0:
            defaults = {
                "watchlist": ",".join(DEFAULT_WATCHLIST),
                "position_size": "0.20",
                "drawdown_freeze": "0.10",
                "confidence_threshold": "0.55",
            }
            for k, v in defaults.items():
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES (?, ?)", (k, v)
                )

        if results_path and results_path.exists():
            results = json.loads(results_path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
                "VALUES (?,?,?,?,?,?)",
                (
                    results["date"],
                    results["train_rows"],
                    results["accuracy"],
                    results["baseline"],
                    results["verdict"],
                    results["notes"],
                ),
            )
            # Extra walk-forward history rows for the chart
            for wf in results.get("walk_forward", []):
                if wf["month"] == "2026-10":
                    continue
                conn.execute(
                    "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        f"{wf['month']}-28",
                        results["train_rows"] - 100,
                        wf["accuracy"],
                        results["baseline"],
                        "Kept" if wf["accuracy"] >= results["baseline"] else "Rejected",
                        "walk-forward month seed",
                    ),
                )

        conn.commit()

    hist = db.read_portfolio_history(db_path)
    last = hist.iloc[-1]
    return {
        "portfolio_value": float(last["value"]),
        "benchmark_value": float(last["benchmark_value"]),
        "cash": float(last["cash"]),
        "drawdown": float(last["drawdown"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed app.db from paper fixtures")
    parser.add_argument(
        "--state",
        type=Path,
        default=ROOT / "fixtures" / "paper_state.json",
    )
    parser.add_argument(
        "--trades",
        type=Path,
        default=ROOT / "fixtures" / "paper_trades.csv",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=ROOT / "results.json",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    totals = seed(args.state, args.trades, args.db, args.results)
    print("Seeded", args.db)
    print(
        f"Dashboard check — portfolio ${totals['portfolio_value']:,.2f} "
        f"benchmark ${totals['benchmark_value']:,.2f} "
        f"cash ${totals['cash']:,.2f}"
    )
    report = ROOT / "fixtures" / "paper_report.md"
    expected = 102340.0
    if abs(totals["portfolio_value"] - expected) > 0.01:
        raise SystemExit(
            f"FAIL: portfolio {totals['portfolio_value']} != paper_report {expected} ({report})"
        )
    print("OK: Dashboard portfolio equals paper_report.md ($102,340.00)")


if __name__ == "__main__":
    main()
