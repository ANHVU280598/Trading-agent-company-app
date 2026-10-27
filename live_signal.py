"""Compute latest raw signals for the watchlist (no trades)."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib

from core.config import DB_PATH, ROOT
from core.data import get_daily_bars
from core.features import build_features
from core.repository import load_settings
from core import db

ET = ZoneInfo("America/New_York")
MODEL_PATH = ROOT / "model.joblib"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    as_of = args.date or datetime.now(ET).strftime("%Y-%m-%d")
    start = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=400)).strftime("%Y-%m-%d")
    settings = load_settings(args.db)
    model = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None

    db.init_db(args.db)
    with db.connect(args.db) as conn:
        for ticker in settings["watchlist"]:
            bars = get_daily_bars(ticker, start, as_of)
            if bars.empty:
                continue
            bars = bars[bars["date"] <= as_of]
            feats = build_features(bars.set_index("date")).dropna()
            if feats.empty:
                continue
            row = feats.iloc[-1]
            price = float(bars.iloc[-1]["close"])
            buy_p = hold_p = sell_p = 1 / 3
            raw = "hold"
            if model is not None:
                proba = model.predict_proba([row[list(model.feature_names_in_)]])[0]
                mapping = {c: float(p) for c, p in zip(model.classes_, proba)}
                buy_p = mapping.get("buy", 0.0)
                hold_p = mapping.get("hold", 0.0)
                sell_p = mapping.get("sell", 0.0)
                raw = max(mapping, key=mapping.get)  # type: ignore[arg-type]
            conn.execute(
                "INSERT OR REPLACE INTO signals(date, ticker, signal, buy_p, hold_p, sell_p, "
                "price, rsi14, drawdown63, sentiment, headline) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    as_of,
                    ticker,
                    raw,
                    buy_p,
                    hold_p,
                    sell_p,
                    price,
                    float(row["rsi14"]),
                    float(row["drawdown63"]),
                    None,
                    None,
                ),
            )
            print(f"{ticker}: {raw} @ {price:.2f}")
        conn.commit()


if __name__ == "__main__":
    main()
