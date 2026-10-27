"""Daily paper agent — reads settings from SQLite, writes signals/trades/portfolio.

Uses Yahoo prices via core.data. No live broker orders. Paper-only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from core.agent import buys_frozen, confidence_gate, position_buy_shares
from core.config import DB_PATH, ROOT, STARTING_PAPER_CASH
from core.data import get_daily_bars
from core.features import build_features
from core.repository import load_settings
from core import db

ET = ZoneInfo("America/New_York")
STATE_PATH = ROOT / "paper_state.json"
TRADES_PATH = ROOT / "paper_trades.csv"
REPORT_PATH = ROOT / "paper_report.md"
MODEL_PATH = ROOT / "model.joblib"


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "cash": STARTING_PAPER_CASH,
        "high_water": STARTING_PAPER_CASH,
        "positions": {},
        "start_date": None,
    }


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def log_trades(rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    if TRADES_PATH.exists():
        prev = pd.read_csv(TRADES_PATH)
        frame = pd.concat([prev, frame], ignore_index=True)
    frame.to_csv(TRADES_PATH, index=False)


def portfolio_value(cash: float, positions: dict, prices: dict[str, float]) -> float:
    total = cash
    for t, pos in positions.items():
        total += float(pos["shares"]) * float(prices.get(t, pos.get("avg_cost", 0)))
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Market date YYYY-MM-DD")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()

    settings = load_settings(args.db)
    as_of = args.date or datetime.now(ET).strftime("%Y-%m-%d")
    start = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=400)).strftime("%Y-%m-%d")

    state = load_state()
    positions = {
        p["ticker"] if isinstance(p, dict) else k: (
            p if isinstance(p, dict) else state["positions"][k]
        )
        for k, p in (
            enumerate(state["positions"])
            if isinstance(state.get("positions"), list)
            else state.get("positions", {}).items()
        )
    }
    # Normalize positions to dict[ticker] -> {shares, avg_cost}
    if isinstance(state.get("positions"), list):
        positions = {
            p["ticker"]: {"shares": p["shares"], "avg_cost": p["avg_cost"]}
            for p in state["positions"]
        }
    else:
        positions = dict(state.get("positions") or {})

    cash = float(state.get("cash", STARTING_PAPER_CASH))
    high_water = float(state.get("high_water", cash))
    prices: dict[str, float] = {}
    signal_rows: list[dict] = []
    new_trades: list[dict] = []

    # Prefer a kept model if present; otherwise HOLD everything (honest demo).
    model = None
    try:
        import joblib

        if MODEL_PATH.exists():
            model = joblib.load(MODEL_PATH)
    except Exception:
        model = None

    for ticker in settings["watchlist"]:
        bars = get_daily_bars(ticker, start, as_of)
        if bars.empty:
            continue
        # Use last available bar on or before as_of
        bars = bars[bars["date"] <= as_of]
        if bars.empty:
            continue
        last = bars.iloc[-1]
        price = float(last["close"])
        prices[ticker] = price
        feats = build_features(bars.set_index("date"))
        row = feats.dropna().iloc[-1] if not feats.dropna().empty else None
        buy_p = hold_p = sell_p = 1 / 3
        raw = "hold"
        if model is not None and row is not None:
            proba = model.predict_proba([row[list(model.feature_names_in_)]])[0]
            classes = list(model.classes_)
            mapping = {c: float(p) for c, p in zip(classes, proba)}
            buy_p = mapping.get("buy", 0.0)
            hold_p = mapping.get("hold", 0.0)
            sell_p = mapping.get("sell", 0.0)
            raw = max(mapping, key=mapping.get)  # type: ignore[arg-type]
        conf = max(buy_p, hold_p, sell_p)
        traded = confidence_gate(raw, conf, settings["confidence_threshold"])
        rsi_val = float(row["rsi14"]) if row is not None else None
        dd63 = float(row["drawdown63"]) if row is not None else None
        signal_rows.append(
            {
                "date": as_of,
                "ticker": ticker,
                "signal": raw,
                "buy_p": buy_p,
                "hold_p": hold_p,
                "sell_p": sell_p,
                "price": price,
                "rsi14": rsi_val,
                "drawdown63": dd63,
                "sentiment": None,
                "headline": None,
            }
        )

        value = portfolio_value(cash, positions, prices)
        dd = value / high_water - 1.0 if high_water else 0.0
        frozen = buys_frozen(dd, settings["drawdown_freeze"])

        if traded == "buy" and ticker not in positions and not frozen:
            shares = position_buy_shares(
                value, cash, price, settings["position_size"]
            )
            if shares > 0:
                cost = shares * price
                cash -= cost
                positions[ticker] = {"shares": shares, "avg_cost": price}
                new_trades.append(
                    {
                        "date": as_of,
                        "ticker": ticker,
                        "action": "buy",
                        "shares": shares,
                        "price": price,
                        "confidence": conf,
                        "status": "Open",
                        "realized_pnl": None,
                    }
                )
        elif traded == "sell" and ticker in positions:
            pos = positions.pop(ticker)
            proceeds = float(pos["shares"]) * price
            pnl = proceeds - float(pos["shares"]) * float(pos["avg_cost"])
            cash += proceeds
            new_trades.append(
                {
                    "date": as_of,
                    "ticker": ticker,
                    "action": "sell",
                    "shares": float(pos["shares"]),
                    "price": price,
                    "confidence": conf,
                    "status": "Closed",
                    "realized_pnl": pnl,
                }
            )

    value = portfolio_value(cash, positions, prices)
    high_water = max(high_water, value)
    dd = value / high_water - 1.0 if high_water else 0.0

    # Benchmark: equal-weight buy-and-hold from start (simplified: track cash-equivalent growth)
    bench = float(state.get("benchmark_value", STARTING_PAPER_CASH))
    if prices:
        # naive: average daily move across watchlist vs previous prices in state
        prev_prices = state.get("last_prices") or prices
        rets = []
        for t, px in prices.items():
            if t in prev_prices and prev_prices[t]:
                rets.append(px / float(prev_prices[t]) - 1.0)
        if rets:
            bench *= 1.0 + sum(rets) / len(rets)

    state.update(
        {
            "as_of": as_of,
            "cash": cash,
            "high_water": high_water,
            "portfolio_value": value,
            "benchmark_value": bench,
            "drawdown": dd,
            "positions": [
                {"ticker": t, "shares": p["shares"], "avg_cost": p["avg_cost"]}
                for t, p in positions.items()
            ],
            "last_prices": prices,
            "start_date": state.get("start_date") or as_of,
        }
    )
    save_state(state)

    db.init_db(args.db)
    with db.connect(args.db) as conn:
        for row in signal_rows:
            conn.execute(
                "INSERT OR REPLACE INTO signals(date, ticker, signal, buy_p, hold_p, sell_p, "
                "price, rsi14, drawdown63, sentiment, headline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
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
                    row["sentiment"],
                    row["headline"],
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO signal_grades(date, ticker, signal, confidence, price_then) "
                "VALUES (?,?,?,?,?)",
                (
                    row["date"],
                    row["ticker"],
                    row["signal"],
                    max(row["buy_p"], row["hold_p"], row["sell_p"]),
                    row["price"],
                ),
            )
        conn.execute(
            "INSERT OR REPLACE INTO portfolio_history(date, value, benchmark_value, cash, drawdown) "
            "VALUES (?,?,?,?,?)",
            (as_of, value, bench, cash, dd),
        )
        conn.execute("DELETE FROM positions")
        for t, p in positions.items():
            conn.execute(
                "INSERT INTO positions(ticker, shares, avg_cost) VALUES (?,?,?)",
                (t, p["shares"], p["avg_cost"]),
            )
        if new_trades:
            for tr in new_trades:
                conn.execute(
                    "INSERT INTO trades(date, ticker, action, shares, price, confidence, status, realized_pnl) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        tr["date"],
                        tr["ticker"],
                        tr["action"],
                        tr["shares"],
                        tr["price"],
                        tr["confidence"],
                        tr["status"],
                        tr["realized_pnl"],
                    ),
                )
            log_trades(new_trades)
        conn.commit()

    REPORT_PATH.write_text(
        f"# Paper report — {as_of}\n\n"
        f"| Metric | Value |\n|--------|-------|\n"
        f"| Portfolio value | ${value:,.2f} |\n"
        f"| Benchmark value | ${bench:,.2f} |\n"
        f"| Cash | ${cash:,.2f} |\n"
        f"| Drawdown from high | {dd * 100:.1f}% |\n"
        f"| Position size setting | {settings['position_size'] * 100:.0f}% |\n",
        encoding="utf-8",
    )
    print(f"paper_trade {as_of}: value=${value:,.2f} cash=${cash:,.2f} trades={len(new_trades)}")


if __name__ == "__main__":
    main()
